"""状态区：属性/道具/金币文本、选手信息与更新线程。"""

import time

from .. import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ..toolkit.api import _api_key
from ..toolkit.texts import _split_status


class StatusMixin:
    def _get_status_text(self):
        return self._status_text

    def _get_attr_text(self):
        return self._attr_text

    def _get_items_text(self):
        return self._items_text

    def _get_gold_text(self):
        return self._gold_text

    def _get_status_data(self):
        return dict(self._last_status)

    def _get_status_locked(self):
        return bool(getattr(self, "_status_locked", False))

    @Slot()
    def toggleStatusLock(self) -> None:
        """锁 / 解锁人物状态：锁住后「读取」不再改状态面板。

        用户："加一个锁，点击后人物状态不会因为读取而改变"。
        """
        self._status_locked = not bool(getattr(self, "_status_locked", False))
        self.statusLockedChanged.emit()

    def _get_status_at(self):
        return self._status_at

    def _apply_status(self, status: dict) -> None:
        """把状态写进界面的三段文本。锁住了就不写（用户要"读取不改状态"）。"""
        if getattr(self, "_status_locked", False):
            return
        attr, items, gold = _split_status(status)
        self._attr_text = attr
        self._items_text = items
        self._gold_text = gold
        self._status_text = "\n".join(t for t in (attr, items, gold) if t)
        # 面板刷新时间：界面上显示"23:51 读取"，数据放了十分钟用户能看出来
        self._status_at = time.strftime("%H:%M")
        self.statusTextChanged.emit()

    # ---- 只刷人物信息（经验下面那个 update 按钮）----
    def _get_updating(self):
        return self._updating

    @Slot()
    def updateStatus(self) -> None:
        """只重新读人物信息，不动地图、不建新层。

        用户："伤害计算的读取为什么任务队列里看不到" —— 它也是一次读取，
        所以在队列里挂一条任务（和读地图/读手册一样能看见「读取中」）；
        失败能重试、跑着能取消。
        """
        import time
        if self._updating:
            return
        from ..constants import TASK_LIMIT
        self._task_seq += 1
        self._update_task = self._task_seq
        self._tasks.insert(0, {"id": self._update_task, "seq": 0,
                               "state": "running", "text": "读取人物状态…",
                               "mode": "status", "started": time.time()})
        del self._tasks[TASK_LIMIT:]
        self.tasksChanged.emit()
        self._updating = True
        self.readingChanged.emit()
        self._start_thread(self._update_worker)

    def _update_worker(self) -> None:
        from ... import trace
        from ...game import read as game_read
        from ...game import towers as tower_mod
        from ...game import winutil

        task_id = getattr(self, "_update_task", None)
        try:
            target = None
            recent = self._last_foreground
            for tower in tower_mod.TOWERS.values():
                if tower.process == recent:
                    target = tower
                    break
            if target is None:
                running = []
                for tower in tower_mod.TOWERS.values():
                    try:
                        if winutil.find_window(tower.process):
                            running.append(tower)
                    except Exception:
                        continue
                target = running[0] if len(running) == 1 else None
            if target is None:
                self._post(lambda: self._finish(
                    "找不到游戏窗口", "把游戏切到前台再点 update",
                    task_id=task_id))
                return

            image = game_read.grab_window(target.process)
            if image is None:
                self._post(lambda: self._finish(
                    "抓不到画面", "游戏窗口可能最小化了", task_id=task_id))
                return

            status = game_read.read_person(image, api_key=_api_key())
            trace.note("update.done", tower=target.name,
                       floor=status.get("floor"), hp=status.get("hp"))

            def apply():
                self._apply_person(target, status)
                # 队列里的那条也要变成"读完了"（被取消的就别改回去了）
                if task_id is not None and task_id not in self._cancelled:
                    self._set_task(task_id, state="done",
                                   text="人物状态已更新")

            self._post(apply)
        except Exception as exc:
            message = repr(exc)[:160]
            trace.note("update.failed", error=message)
            self._post(lambda: self._finish("更新失败", message,
                                            task_id=task_id))
        finally:
            self._post(self._update_done)

    def _update_done(self) -> None:
        self._updating = False
        task_id = getattr(self, "_update_task", None)
        if task_id is not None:
            # 被取消的那条不要改回去（cancelTask 已经写成"已取消"）
            for task in self._tasks:
                if task.get("id") == task_id and task.get("state") == "running":
                    self._set_task(task_id, state="done",
                                   text="人物状态已更新")
                    break
        self.readingChanged.emit()

    def _apply_person(self, tower, status) -> None:
        """把 update 读到的字段合并进当前状态（只覆盖读到值的字段）。"""
        if getattr(self, "_status_locked", False):
            return
        if not isinstance(status, dict) or "_error" in status:
            return
        merged = dict(self._last_status)
        for key, value in status.items():
            if key.startswith("_"):
                continue
            if value in (None, "", {}, []):
                continue
            merged[key] = value
        self._tower_label = tower.name
        self._last_tower = tower
        self._last_status = merged
        self._apply_status(merged)
