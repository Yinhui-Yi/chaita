"""把一次读取的结果并进那一条层记录：层名归一、怪按手册写法归一、
资源按图标身份合并，最后通知界面。

`_apply_floor` 也在这儿：层号一读出来就先把那条记录建好，怪和资源随之填。"""

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

from .common import _count_of

from PySide6.QtCore import Slot


class ReadingDeliverMixin:
        def _deliver(self, tower, result, seq: int = 0, entry_id=None,
                     quick_map=None, task_id=None, mode: str = "auto") -> None:
            """把一次读取的结果落到界面上。

            seq 只用来决定"谁可以改状态面板"：并行的几次会乱序回来，让最后一次点击
            的结果永远赢，否则旧层的数据会盖掉新层。
            quick_map 是本地先裁好的截图，用它省一次落盘。
            """
            if task_id in self._cancelled:
                return
            self._error_text = ""

            # 读的是怪物手册：记录怪物，不动地图和属性
            if result.kind == "monsters":
                outcome = self._deliver_monsters(result)
                if outcome is not None:
                    added, skipped = outcome
                    text = "手册 %d 只" % len(result.monsters or [])
                    if added or skipped:
                        text += "（新增 %d" % added
                        text += ("，%d 只已记过）" % skipped) if skipped else "）"
                    self._set_task(task_id, state="done", text=text)
                return

            status = result.status
            if "_error" in status:
                self._finish("模型输出无法解析", str(status.get("_raw", ""))[:80],
                             task_id=task_id)
                return

            # 只读地图：只更新"我在哪"（顶栏的层数），人物面板一个字段都不动
            if mode == "map":
                self._tower_label = result.name or tower.name
                self.statusTextChanged.emit()
            # 状态面板只让序号最大的那次写
            elif seq >= self._status_seq:
                self._status_seq = seq
                self._tower_label = result.name or tower.name
                # 锁住人物状态：读取只更新地图/怪，状态面板不动
                if not getattr(self, "_status_locked", False):
                    # 必须先存 _last_status 再 _apply_status：后者会发信号让 QML 读
                    # statusData，顺序反了 QML 拿到的还是上一局的数据。
                    self._last_tower = tower
                    self._last_status = dict(status)
                    self._apply_status(status)

            # 本层怪物：模型报的名字 + 它估的只数（估不出来就是 null）。
            # 名字先对到手册的写法上：图上没字，模型是看图案猜的，猜出来的别名
            # （「绿头怪」这种）不该进记录（用户："哪里来的绿头怪、红头怪"）。
            known = [str(m.get("name") or "").strip() for m in self._monsters
                     if str(m.get("name") or "").strip()]
            read_names = [str((row or {}).get("name") or "").strip()
                          for row in (result.monsters or [])]
            mapping, unmatched, invented = monster_names.align(read_names, known)
            dropped = set(unmatched) if known else set()
            if mapping or dropped:
                from .... import trace
                trace.note("read.name_align", renamed=len(invented),
                           dropped=len(dropped), unmatched=sorted(dropped)[:5])
            here = []
            for monster in (result.monsters or []):
                name = str(monster.get("name") or "").strip()
                if not name or name in dropped:
                    continue
                name = mapping.get(name, name)
                count = monster.get("count")
                if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                    count = None
                here.append({"name": name, "count": count})

            floor = status.get("floor")
            floor_text = _floor_text(floor)
            if not floor_text:
                # 没读出层数就不进地图列表：一条没有层数的记录对用户没意义，
                # 还会占着"识别中/读取超时"这种空壳。
                from .... import trace
                trace.note("read.no_floor", seq=seq, raw=str(status)[:120])
                self._chat_reply = "这次没读出层数，地图列表不记录"
                self.chatReplyChanged.emit()
                self.statusTextChanged.emit()
                self._set_task(task_id, state="failed", text="没读出层数")
                return

            self._store_map_entry(tower, result, entry_id, floor_text, here,
                                  items=result.items or [], quick_map=quick_map,
                                  grid=result.grid or {})
            # 主结果先到位，但资源还在后面读：任务行只写层名（行首的"…"已经表示在跑），
            # 不再拼"（读资源…）"这种内部进度黑话
            self._set_task(task_id, state="running", text=floor_text)

        def _apply_floor(self, tower, floor_text, map_image, task_id=None) -> None:
            """层数一读出来就先落地：地图那条先建好，怪物/资源随后再填。"""
            if task_id in self._cancelled:
                return
            floor_text = _floor_text(floor_text)
            if not floor_text:
                return
            index = -1
            for position, entry in enumerate(self._map_history):
                if entry.get("floor") == floor_text:
                    index = position
                    break

            url = ""
            if index >= 0:
                url = str(self._map_history[index].get("url") or "")
            if not url and map_image is not None:
                self._frame += 1
                url = _save_temp(map_image, "map_%s_%d" % (tower.key, self._frame))

            if index >= 0:
                entry = dict(self._map_history[index])
                entry["floor"] = floor_text
                if url:
                    entry["url"] = url
                self._map_history[index] = entry
            else:
                self._map_history.insert(0, {"floor": floor_text, "url": url,
                                             "mons": [], "items": []})
            self.mapHistoryChanged.emit()
            self._set_task(task_id, state="running", text=floor_text)

        def _align_floor_rows(self) -> int:
            """手册读到名字以后，把地图上"模型自己起的名字"改成手册的写法。

            用户："刷新第0层怪物手册里出现了垃圾词条还覆盖了我的正确怪物词条" ——
            早期读地图时手册还是空的，模型把"红色史莱姆"叫成"红史莱姆"；等手册读到
            真名，这些旧行没人再对一遍，就一直挂着当"多出来的怪"。

            **只改名，不写数量、不动勾/图标/手改过的效果**（用户说"不要回填"是指不许用
            手册数据改地图；把名字纠正过来是另一件事）。两行对上同一只的并成一行，
            数量取大的 —— 两行存的都是"这一层一共有几只"，相加会翻倍。
            """
            from .... import trace
            known = [str(m.get("name") or "").strip() for m in self._monsters
                     if str(m.get("name") or "").strip()]
            if not known:
                return 0
            renamed = 0
            for entry in self._map_history:
                rows = entry.get("mons") or []
                if not rows:
                    continue
                mapping, _, _ = monster_names.align(
                    [str(row.get("name") or "") for row in rows], known)
                if not mapping:
                    continue
                merged = []
                index_of = {}
                for row in rows:
                    item = dict(row)
                    old = str(item.get("name") or "")
                    name = mapping.get(old, old)
                    if name != old:
                        item["name"] = name
                        renamed += 1
                    if name and name in index_of:
                        kept = index_of[name]
                        if _count_of(item) > _count_of(merged[kept]):
                            merged[kept] = item
                        continue
                    if name:
                        index_of[name] = len(merged)
                    merged.append(item)
                entry["mons"] = merged
            if renamed:
                self.mapHistoryChanged.emit()
                trace.note("manual.align_floors", renamed=renamed)
            return renamed

        def _deliver_monsters(self, result) -> None:
            """手册读取结果：**只追加没记过的怪**，同名的原样不动。

            用户："为什么第二次读取怪物会覆盖我修改过的怪物信息，同名怪物不用修改" ——
            手册是参考，列表里的记录是用户自己改过的（生命/攻防/技能/技能参数/金币）。
            再读一次只补新怪，已经在名单里的一个字段都不碰。
            新怪带一张从手册上裁下来的图案（模型给框、代码换算裁剪）。
            """
            entries = result.monsters or []
            if not entries:
                self._finish("没读到怪物", "打开怪物手册/图鉴后再点「读取」")
                return

            known = {(m.get("name") or "").strip() for m in self._monsters}
            monsters = list(self._monsters)
            added = 0
            skipped = 0
            for entry in entries:
                raw = str(entry.get("name") or "未知").strip()
                # 手册页上的名字是印着的**真名**，所以这里只认"一模一样"和"缩写"
                # （strict=True）。不能走"最像的那个"：小蝙蝠/大蝙蝠共两个字，会被判成
                # 同一只 —— 读了两只只记一只（用户："读取记录显示读取两只但看怪物只有一只"）。
                name = monster_names.match_one(raw, list(known), strict=True) or raw
                if name in known:
                    skipped += 1               # 同名：不覆盖用户改过的信息
                    continue
                icon = entry.get("icon")
                icon_url = ""
                if icon is not None and getattr(icon, "size", 0) > 0:
                    self._frame += 1
                    # 原样存，不放大：放大是预处理，用户明确禁止；显示尺寸交给 QML
                    icon_url = _save_temp(icon, "mon_%d" % self._frame)
                skill_text = entry.get("skills", "") or ""
                monsters.append({
                    "name": name,
                    "hp": entry.get("hp", ""),
                    "atk": entry.get("atk", ""),
                    "def": entry.get("def", ""),
                    "exp": entry.get("exp", ""),
                    "skills": skill_text,
                    "skill_items": _fill_skill_codes(_skill_items_from_text(skill_text)),
                    "count": entry.get("count"),
                    "icon": icon_url,
                })
                known.add(name)
                added += 1

            if added:
                self._monsters = monsters
                self.monstersChanged.emit()

            # 手册里有名字了：把地图上那些"模型自己起的名字"改成手册的写法
            # （只改名，不碰数量/勾/图标）。不这么做的话，旧名字会永远挂着，
            # 在「怪物」栏里当成多出来的怪显示（用户："垃圾词条覆盖了我的正确词条"）。
            self._align_floor_rows()

            # 到这里就结束：读怪物**只动"怪物"这一栏**，而且只往后面加。
            # 不回填地图那一层（owner 明确要求："不要回填！！！"）：地图里的怪只由
            # 「读地图」「＋ 加怪」「↻」和用户手动编辑来改；连"这一层各有几只"也不问
            # （那是 ↻ 的事）。以前这里会整段替换那一层的怪、再自动发一次统计。

            # 注意别在这里写 self._reading = False：并行时还有别的任务在跑，
            # 按钮状态只由 _active 决定（见 _job_done）。
            if added:
                extra = ("，%d 只已经记过" % skipped) if skipped else ""
                self._chat_reply = ("已记录 %d 只怪物（新增 %d%s）"
                                    % (len(self._monsters), added, extra))
            else:
                self._chat_reply = "这 %d 只都记过了，没动你改过的记录" % len(entries)
            self.chatReplyChanged.emit()
            return added, skipped
