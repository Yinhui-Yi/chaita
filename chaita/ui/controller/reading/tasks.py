"""一次读取任务的生命周期：开工 → 抓图 → 问模型 → 收尾。

任务队列里那一行（跑着/完成/失败）就是这里在改；抓图失败、读图超时
这些兜底也都在这里，别处不重复判。"""

import time

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...constants import TASK_LIMIT
from ...toolkit.api import _api_key
from ...toolkit.diagnostics import _write_error_log
from ...toolkit.library import _fill_skill_codes, _skill_items_from_text
from ...toolkit.pictures import _save_temp, _save_thumb
from ...toolkit.texts import _carry_row, _floor_text

from ....game import monster_names

import time

from PySide6.QtCore import Slot


class ReadingTasksMixin:
    @Slot(str)
    def readOnly(self, mode: str) -> None:
        """分段读取：怪物段只读手册，地图段只读地图。

        分开的理由：用户自己决定现在读哪一块，不用先猜画面类型；
        画面不符合时给一句明确提示，而不是静默读错。
        """
        self._start_task(None, mode=mode)

    @Slot()
    def readGame(self) -> None:
        """点「读取」：每点一次起一个独立任务，互不等待，真并行。

        每次任务自己抓图、自己发请求、自己带序号回来填自己那条地图记录。
        乱序返回没关系：地图条目按层数归并，状态面板只让序号最大的那个写。
        """
        self._start_task(None)

    @Slot(int)
    def retryTask(self, task_id: int) -> None:
        """重试一条失败的任务：**用当初那张截图**重读，不重新抓屏。

        重新抓屏是没有意义的：用户看到的是"这一次读失败了"，想重试的是同一张画面。
        画面已经变了还抓新的，等于换了个任务。

        「读取人物状态」那条没有截图可复用：重试就是再读一次人物面板。
        """
        mode = "auto"
        for task in self._tasks:
            if task.get("id") == task_id:
                mode = str(task.get("mode") or "auto")
                break
        if mode == "status":
            self._cancelled.discard(task_id)
            self._tasks = [task for task in self._tasks
                           if task.get("id") != task_id]
            self.tasksChanged.emit()
            self.updateStatus()
            return
        image = self._load_task_src(task_id)
        self._cancelled.discard(task_id)
        self._start_task(task_id, image=image, mode=mode)

    @Slot(int)
    def cancelTask(self, task_id: int) -> None:
        """取消一条正在读取的任务：结果回来直接丢掉。"""
        self._cancelled.add(task_id)
        self._set_task(task_id, state="cancelled", text="已取消")
        from .... import trace
        trace.note("read.cancelled", task=task_id)

    def _start_task(self, task_id, image=None, mode: str = "auto") -> None:
        from .... import trace
        self._map_seq += 1
        seq = self._map_seq

        if task_id is None:
            self._task_seq += 1
            task_id = self._task_seq
            self._tasks.insert(0, {"id": task_id, "seq": seq,
                                   "state": "running", "text": "读取中…",
                                   # 记下这次读的是地图还是怪物手册：界面上两个按钮、
                                   # 记录里也要能分开（重试还要沿用同一个）
                                   "mode": mode or "auto",
                                   "started": time.time()})
            del self._tasks[TASK_LIMIT:]
            self.tasksChanged.emit()
        else:
            # 重试也要重新记开始时间：界面上要显示"这一轮跑了多久"
            self._set_task(task_id, state="running", text="读取中…", seq=seq,
                           mode=mode or "auto", started=time.time())

        self._active += 1
        self._reading = True
        self._error_text = ""
        self._status_text = "读取中…"
        self.readingChanged.emit()
        self.statusTextChanged.emit()
        self.chatReplyChanged.emit()
        trace.note("read.start", seq=seq, task=task_id, active=self._active,
                   foreground=self._last_foreground)
        try:
            self._start_thread(self._read_worker, (seq, task_id, image, mode))
        except Exception as exc:
            # 线程都起不来（极少见），直接把这次的计数退掉，不能让按钮卡住
            trace.note("read.thread_failed", seq=seq, error=repr(exc)[:200])
            message = repr(exc)[:160]
            self._active = max(0, self._active - 1)
            self._reading = self._active > 0
            self._finish("起不了读取线程", message, task_id=task_id)
            self.readingChanged.emit()

    def _capture(self, seq, task_id, image, tower_mod, capture_mod):
        """点下去的那一刻先抓一帧：解析窗口 → 抓图 → 把缩略图挂到任务行上。

        只 import 轻量模块（win32 / cv2），不碰 AI。返回 (target, image)；
        出错时已经排好失败提示，返回 (None, None)。
        """
        from .... import trace
        foreground = self._last_foreground
        target = capture_mod.find_target(tower_mod.TOWERS, foreground)
        if image is None:
            if target is None:
                detail = capture_mod.describe_failure(tower_mod.TOWERS,
                                                      foreground)
                self._post(lambda: self._finish("前台不是游戏窗口", detail,
                                                task_id=task_id))
                return None, None
            image = capture_mod.grab(target.process)
            if image is None:
                self._post(lambda: self._finish(
                    "抓不到画面", "游戏窗口可能最小化了，恢复后再点「读取」",
                    task_id=task_id))
                return None, None
            # 抓完立刻出缩略图：用户马上看到"截到了"，之后才等模型
            thumb = _save_thumb(image, "task_%d" % seq, width=900)
            if thumb:
                self._post(lambda: self._set_task(task_id, url=thumb))
            trace.note("read.grab", seq=seq, target=target.name,
                       image=list(image.shape))
        return target, image

    def _read_worker(self, seq: int, task_id=None, image=None,
                     mode: str = "auto") -> None:
        # 注意：import 也必须写在 try 里面。原来放在外面，只要这几行抛异常
        # （导入失败、名字写错），finally 就不会执行，_active 永远不减，
        # 按钮就永久卡在"读取中"——并行任务的收尾必须是无条件的。
        entry_id = None
        try:
            # 先抓一帧再 import AI：read 会拖进 agent_framework → openai（1.5-2 s），
            # 放在截图后面，模型看到的才是"点下去那一刻"的画面。
            from ....game import capture as capture_mod
            from ....game import towers as tower_mod

            target, image = self._capture(seq, task_id, image, tower_mod,
                                          capture_mod)
            if target is None:
                return
            from ....game import read as game_read
            from ....game import winutil

            entry_id = self._read_worker_once(seq, task_id, game_read,
                                              tower_mod, winutil, image,
                                              mode, target=target)
        except BaseException as exc:        # 兜底：任何异常都不能让按钮卡住
            from .... import trace
            trace.note("read.crashed", seq=seq, error=repr(exc)[:300])
            # 注意：不能在 lambda 里引用 exc —— Python 出了 except 块就把 exc 删了，
            # 排到主线程执行时才报 NameError，收尾就半途而废（实测踩过）。
            message = repr(exc)[:160]
            self._post(lambda: self._finish("读取异常", message, task_id=task_id))
        finally:
            self._post(self._job_done)

    def _read_worker_once(self, seq: int, task_id, game_read, tower_mod,
                          winutil, image=None, mode: str = "auto", target=None):
        from .... import trace
        key = _api_key()
        if not key:
            self._post(lambda: self._finish(
                "没配置 API key",
                "在项目根目录 config.yaml 里填 api_key，或设置环境变量 DEEPSEEK_API_KEY",
                task_id=task_id))
            return None

        # 只读"用户刚才在看的那个窗口"里的游戏，绝不按固定顺序挨个试。
        # 挨个试的后果实测过：两座塔都开着时先命中的那个永远赢，用户看着 A
        # 点读取却读到 B，看起来就是"点了没用"。
        if target is None:
            target = None
            recent = self._last_foreground
            if recent:
                for tower in tower_mod.TOWERS.values():
                    if tower.process == recent:
                        target = tower
                        break

        if target is None:
            # 兜底：整台机器上只开着一个游戏窗口时，就按它读。
            # 否则用户切到别的窗口再回来点读取，会莫名被判"前台不是游戏窗口"。
            running = []
            for tower in tower_mod.TOWERS.values():
                try:
                    if winutil.find_window(tower.process):
                        running.append(tower)
                except Exception:
                    continue
            if len(running) == 1:
                target = running[0]
            else:
                what = recent or "（没采样到）"
                detail = ("刚才在前台的是：%s\n请把游戏窗口切到前台，再点「读取」。"
                          % what)
                if len(running) > 1:
                    detail += "\n同时开着 %d 个游戏窗口，没法判断该读哪个。" % len(running)
                self._post(lambda: self._finish("前台不是游戏窗口", detail,
                                                task_id=task_id))
                return

        # ---- 图已经在 _capture 里抓好了（点下去那一刻）----
        # 只有直接调用/重试没带图时才在这里补抓一次。
        if image is None:
            try:
                image = game_read.grab_window(target.process)
            except Exception:
                image = None
        if image is None:
            self._post(lambda: self._finish(
                "抓不到画面", "游戏窗口可能最小化了，恢复后再点「读取」",
                task_id=task_id))
            return None

        # 把这次用的图存一份挂到任务上：重试时直接用它，不再重新抓屏
        src_url = ""
        try:
            self._frame += 1
            src_url = _save_temp(image, "task_src_%d" % seq)
        except Exception:
            src_url = ""
        if src_url:
            self._post(lambda: self._set_task(task_id, src=src_url))

        try:
            screen = game_read.classify(image, api_key=key)
        except Exception:
            screen = "map"      # 判不出来就当地图，别把这次读取整个丢掉
        trace.note("read.screen", seq=seq, screen=screen, mode=mode)

        # 分段读取时先核对画面：读怪物要求手册页，读地图要求地图页。
        # 不符合就直接说清楚，别把另一类内容读进来（那会覆盖掉已有的记录）。
        if mode == "monsters" and screen != "manual":
            self._post(lambda: self._finish(
                "现在不是怪物手册",
                "请先打开怪物手册/图鉴，再点「读怪物」。", task_id=task_id))
            return None
        if mode == "map" and screen == "manual":
            self._post(lambda: self._finish(
                "现在是怪物手册",
                "请先回到地图画面，再点「读地图」。", task_id=task_id))
            return None

        # ---- 第二步：确认是地图，就先把截图裁出来备着 ----
        # 注意：不提前插列表条目。列表里每一条都代表"某一层"，层数没读出来就摆一条
        # 上去只会多出一个"识别中…/读取超时"的空壳（用户原话：没读出层数就别展示）。
        entry_id = "s%d" % seq
        quick = game_read.map_snapshot(target, image) if screen != "manual" else None

        # 任务队列里每行左边显示"这次读进来的图"。
        # 用**整窗截图**，不用裁出来的地图区：层数、生命这些在左边的面板里，
        # 裁成地图就把它们截掉了，看缩略图根本不知道这是哪一层。
        thumb = _save_thumb(image, "task_%d" % seq, width=900)
        if thumb:
            self._post(lambda: self._set_task(task_id, url=thumb))

        trace.note("read.target", seq=seq, tower=target.name,
                   process=target.process,
                   image=None if image is None else list(image.shape))
        started = time.monotonic()

        # ---- 第三步：整张截图交给模型，把内容读出来 ----
        # 层数一读出来就先把地图那条建好（图 + 层数），其余信息随后再填
        def _on_floor(floor_text, map_image):
            if not floor_text:
                return
            self._post(lambda: self._apply_floor(target, floor_text,
                                                map_image, task_id))

        try:
            if mode == "map":
                # 只读地图：层数 + 地图截图；**不调用 read()**，
                # 因为 read() 会顺带再读一遍人物面板并把状态覆盖掉
                floor_only = game_read.read_floor(image, api_key=key)
                snap = game_read.map_snapshot(target, image)
                if floor_only:
                    try:
                        _on_floor(floor_only, snap)
                    except Exception:
                        pass
                # 用真正的 Reading 类（game_read 在测试里是替身模块）
                from ....game.read import Reading as _Reading
                result = _Reading(
                    status={"floor": floor_only}, map=snap,
                    name=target.name, raw="", kind="map",
                    monsters=[], items=[])
            else:
                # 面板里已有的怪名当"候选名字"传给读地图：同一张图上「红史莱姆 /
                # 红头怪」「蓝蝙蝠 / 紫蝙蝠」这种最容易飘，给候选能让它对齐手册写法。
                # 只传名字，不参与看图、不替模型判断。
                known = [str(m.get("name") or "").strip()
                         for m in self._monsters
                         if str(m.get("name") or "").strip()]
                result = game_read.read(target, api_key=key, image=image,
                                        screen=screen, on_floor=_on_floor,
                                        known=known)
        except Exception as exc:
            trace.note("read.failed", seq=seq,
                       seconds=round(time.monotonic() - started, 1),
                       tower=target.name, error=repr(exc)[:200])
            # exc 出了 except 块就没了，必须先转成字符串再排进队列
            detail = "%s\n%s" % (target.name, exc)
            self._post(lambda: self._finish("读不到局面", detail,
                                            task_id=task_id))
            return entry_id
        trace.note("read.done", seq=seq,
                   seconds=round(time.monotonic() - started, 1),
                   kind=result.kind, monsters=len(result.monsters or []))
        self._post(lambda: self._deliver(target, result, seq, entry_id, quick,
                                         task_id=task_id, mode=mode))
        # 资源只在「读取」（整窗读）里补：读地图就只读地图。
        # 用户明确要求：读地图别顺带读资源，那和顶部「读取」重复。
        if result.kind != "monsters" and mode == "auto" \
                and not (result.items or []):
            # 资源已经在「读地图」那个会话里问过（result.items）就不再发第二次；
            # 只有整窗「读取」漏了资源时才补这一步。
            focus = quick if quick is not None else image
            self._start_items_task(game_read, focus, key,
                                   _floor_text(result.status.get("floor")),
                                   task_id)
        elif result.kind != "monsters":
            self._post(lambda: self._finish_items_task(
                task_id, _floor_text(result.status.get("floor")), got_items=True))
        return entry_id

    def _finish(self, headline: str, detail: str, task_id=None) -> None:
        # 失败的这次在任务队列里标红，并给一个重试按钮
        self._set_task(task_id, state="failed",
                       text=(headline + "：" + detail.splitlines()[0])[:40])
        self._tower_label = ""
        self._attr_text = headline
        self._items_text = ""
        self._gold_text = ""
        self._status_text = "%s\n%s" % (headline, detail)
        # 底部那条不再重复同一句：失败原因已经写在上面那行红字和记录行里了。
        # （以前同一句话在上面红字、记录行、底部栏各出现一次，纯噪音。）
        self._chat_reply = ""
        # 界面上那条红字 + 落一份到 docs/capture/last_error.txt：
        # 读不出来时得能立刻知道是"前台不是游戏"还是"模型解析失败"，不然只能瞎猜
        self._error_text = "%s：%s" % (headline, detail.replace("\n", " "))[:160]
        _write_error_log(headline, detail)
        # 这里同样不碰 _reading：并行时其它任务还在跑，按钮只跟 _active 走
        self.statusTextChanged.emit()
        self.chatReplyChanged.emit()
