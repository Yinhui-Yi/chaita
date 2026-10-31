"""「刷新本层」：拿这一层已经存下来的地图截图，问模型「这层有哪些怪、各几只、
有哪些资源」，再把结果并进记录（读不到的不删，只更新数量）。"""

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

from ..floors.common import _align_grid_names
from .common import _count_of

from PySide6.QtCore import Slot


class ReadingScanMixin:
        def _start_scan_task(self, image_url, floor_text, task_id=None) -> None:
            """用那层的地图截图读"这层有哪些怪、各几只"，回来写进 mons。

            和以前那个 `_start_count_task` 的区别：**不要求先有名单**。以前只能
            "给定名字填数字"，一层没加过怪就什么都做不了（owner：「刷新会读图并
            统计有哪些怪吗」）—— 现在直接把图上的怪列出来。
            """
            self._counting_floor = floor_text
            self.countingChanged.emit()

            def done(state, text):
                self._counting_floor = ""
                self.countingChanged.emit()
                if task_id is not None:
                    self._set_task(task_id, state=state, text=text)

            def run():
                from .... import trace
                from ....game import read as game_read
                try:
                    import cv2
                    import numpy as np
                    real = image_url.replace("file:///", "")
                    data = np.fromfile(real, dtype=np.uint8)
                    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
                except Exception as exc:
                    trace.note("scan.load_failed", error=repr(exc)[:120])
                    self._post(lambda: done("failed", "统计失败：截图读不出来"))
                    return
                if image is None:
                    self._post(lambda: done("failed", "统计失败：截图读不出来"))
                    return
                # 手册里的怪名只当"优先用这些名字"的提示，不是必须
                known = [str(m.get("name") or "").strip() for m in self._monsters
                         if str(m.get("name") or "").strip()]
                try:
                    data = game_read.read_floor_map(image, api_key=_api_key(),
                                                    known=known)
                except Exception as exc:
                    trace.note("scan.failed", error=repr(exc)[:200])
                    data = {}
                monsters = (data or {}).get("mons") or []
                items = (data or {}).get("items") or []
                grid = (data or {}).get("grid") or {}
                if monsters or items:
                    self._post(lambda: self._apply_scan(floor_text, monsters,
                                                        task_id=task_id,
                                                        items=items, grid=grid))
                else:
                    self._post(lambda: done("failed", "统计失败：没认出怪和资源"))

            self._start_thread(run)

        def _apply_scan(self, floor_text, monsters, task_id=None, items=None,
                        grid=None) -> None:
            """把"读图认出来的怪 + 资源"并进那一层。

            合并规则（信息能少丢就少丢）：
            - 已有的条目：保住它的**顺序**、「拿过了」的勾/图标/手改过的效果，
              只更新数量；
            - 图上新出现的：追加到末尾；
            - 图上没读到的旧条目**不删** —— 读一次就把用户手动加的清掉，风险太大。

            grid = 这次一起读到的「每个格子里有什么」（`docs/ROUTE.md` 的路线链预填用）；
            同一次读里读到的格子，顺手写进这条记录。

            同一种东西**只留一行**（用户："我二次刷新时，地图的怪和资源会累计"）：
              · 怪：按手册的写法归一（绿头怪 / 青头怪 是同一只），老行也一起归一；
              · 资源：按**图标**归一（红药水 / 红血瓶 都是 potion_red）。
            以前模型这次叫一个名、下次叫另一个名，就当成新条目追加上去，越刷越多。
            """
            from .... import trace
            from ....game import iteminfo
            if task_id is not None:
                self._counting_floor = ""
                self.countingChanged.emit()
            # 资源：先按"图标身份"把这一次读到的同种资源并起来
            found_items = {}
            for row in (items or []):
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                if not name:
                    continue
                try:
                    count = int(row.get("count") or 0)
                except (TypeError, ValueError):
                    continue
                if count <= 0:
                    continue
                key = iteminfo.key_for(name)
                slot = found_items.setdefault(key, {"name": name, "count": 0})
                slot["count"] += count
            for position, entry in enumerate(self._map_history):
                if entry.get("floor") != floor_text:
                    continue
                # 图上没有字，模型是看图案猜名字的：先把它对到手册里的写法上
                # （用户："刷新地图的时候不看已经读的怪物的？"）。
                # 手册里有名字、这个名字又对不上任何一个 → 不记，免得凭空多出
                # 「绿头怪 / 红头怪」这种不属于这座塔的名字。
                known = [str(m.get("name") or "").strip() for m in self._monsters
                         if str(m.get("name") or "").strip()]
                read_names = [str((row or {}).get("name") or "").strip()
                              for row in monsters]
                mapping, unmatched, invented = monster_names.align(read_names, known)
                dropped = set(unmatched) if known else set()
                # 老行也按同一张表归一（只改名，别的字段一个不动）
                existing = list(entry.get("mons") or [])
                old_names = [str(m.get("name") or "") for m in existing]
                old_map, _, _ = monster_names.align(old_names, known)
                if mapping or dropped or old_map:
                    trace.note("scan.name_align", floor=floor_text,
                               renamed=len(invented), dropped=len(dropped),
                               renamed_old=len(old_map),
                               unmatched=sorted(dropped)[:5])
                found = {}
                for row in monsters:
                    name = str(row.get("name") or "").strip()
                    if not name or name in dropped:
                        continue
                    name = mapping.get(name, name)
                    try:
                        count = int(row.get("count") or 0)
                    except (TypeError, ValueError):
                        continue
                    found[name] = found.get(name, 0) + count
                mons = []
                index_of = {}
                added = 0
                for monster in existing:
                    raw = str(monster.get("name") or "")
                    name = old_map.get(raw, raw)
                    item = dict(monster)
                    if name:
                        item["name"] = name
                    if name in found:
                        item["count"] = found[name]
                    if name and name in index_of:
                        # 同一个名字出现了两行（以前刷累计出来的）：只留一行，
                        # 数量取大的（两行存的都是"这一层的总数"，相加会翻倍）
                        kept_at = index_of[name]
                        if _count_of(item) > _count_of(mons[kept_at]):
                            mons[kept_at] = item
                        continue
                    if name:
                        index_of[name] = len(mons)
                    mons.append(item)
                for name, count in found.items():
                    if name in index_of:
                        continue
                    mons.append(_carry_row(None, {"name": name, "count": count}))
                    added += 1
                updated = dict(entry)
                updated["mons"] = mons

                # 资源：同一种东西按图标身份合并（红药水 / 红血瓶 是一瓶）
                entries_added = 0
                kept = []
                seen_items = {}
                for item in (entry.get("items") or []):
                    name = str(item.get("name") or "")
                    key = iteminfo.key_for(name)
                    if key and key in seen_items:
                        continue                 # 同一种资源的第二行：去掉
                    copy = self._fill_item_display(item)
                    if key in found_items:
                        copy["count"] = found_items[key]["count"]
                    if key:
                        seen_items[key] = True
                    kept.append(copy)
                for key, slot in found_items.items():
                    if key in seen_items:
                        continue
                    # AI 只给名字和数量：图标/效果在这儿按道具表补好（用户："读进来的
                    # 资源还是没有图标"）—— 存进来的记录自己就是完整的，不靠界面兜底
                    kept.append(self._fill_item_display(
                        {"name": slot["name"], "count": slot["count"],
                         "effect": "", "icon": ""}))
                    entries_added += 1
                updated["items"] = kept
                if grid:
                    # 和这一层的怪清单同一套归一：模型看图案猜的名字 → 手册的写法
                    updated["grid"] = _align_grid_names(grid, self._monsters)

                self._map_history[position] = updated
                self.mapHistoryChanged.emit()
                trace.note("scan.applied", floor=floor_text,
                           found=len(found), added=added, total=len(mons),
                           items=len(found_items), items_added=entries_added)
                if task_id is not None:
                    text = ("%s：%d 种怪（新增 %d）· %d 种资源（新增 %d）"
                            % (floor_text, len(found), added,
                               len(found_items), entries_added))
                    if dropped:
                        text += " · 忽略 %d 个对不上手册的名字" % len(dropped)
                    self._set_task(task_id, state="done", text=text)
                return
            if task_id is not None:
                self._set_task(task_id, state="failed", text="统计失败：这层不见了")
