"""每层记录本身：建/删/改名、备忘、刷新入口、地图历史；资源行补图标和效果也在这儿。"""

import time

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...constants import TASK_LIMIT
from ...toolkit.pictures import _save_temp

from .common import (_align_grid_names, _dead_icon_file, _drop_unknown_monsters,
                     is_manual, merge_cells)
from .stairs import _stairs_list


def _stairs_from_grid(cells) -> list:
    """从"每格有什么"里挑出楼梯：`[{row, col, dir, to:""}]`（通哪层留空给人选）。

    用户 2026-10-30："谁告诉你一层只有一个上楼或下楼的？谁告诉你0层就一定去1层的？"
    —— 模型只认得出"这格是级台阶、朝上还是朝下"，通到哪一层是游戏设定，它看不到，
    所以 `to` 留空，界面上那一行点一下自己选。
    """
    out = []
    for cell in cells or []:
        if not isinstance(cell, dict):
            continue
        kind = str(cell.get("kind") or "")
        if kind not in ("stair_up", "stair_down"):
            continue
        try:
            row = int(cell.get("row"))
            col = int(cell.get("col"))
        except (TypeError, ValueError):
            continue
        out.append({"row": row, "col": col,
                    "dir": "up" if kind == "stair_up" else "down", "to": ""})
    return out


def _merge_stairs(old, from_grid) -> list:
    """楼梯：**用户定过的原样保留**，其余按这次读到的重建。

    以前是"只补不改"（同格保留用户选过的目标层），但那样 AI 读到的楼梯会一次比
    一次多（用户："我二次刷新时，地图的怪和资源会累计"）。现在和格子一个规则：
    用户动过那行（改过方向/目标层/落点）就整行留着，没动过的按这次读到的重来。
    """
    merged = [dict(one) for one in (old or []) if is_manual(one)]
    taken = {(int(one.get("row", -1)), int(one.get("col", -1)))
             for one in merged}
    for fresh in from_grid or []:
        if (fresh["row"], fresh["col"]) in taken:
            continue
        merged.append(dict(fresh))
    return merged


class RecordsMixin:
    def _find_floor(self, floor_text):
        for position, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                return position
        return -1

    def _store_map_entry(self, tower, result, entry_id, floor_text,
                         quick_map=None, grid=None) -> None:
        """把这次的地图落到层数相同的那条记录上（没有就插一条）。

        grid = 每个格子里有什么 —— **它就是这一层的清单和坐标**（`_merge_read_grid`）。
        这次没读到格子就保留那条记录上原来的：读地图只更新层号和截图。
        """
        index = -1
        for position, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                index = position
                break

        url = ""
        image = quick_map if quick_map is not None else result.map
        if index >= 0:
            url = str(self._map_history[index].get("url") or "")
        if image is not None and not url:
            self._frame += 1
            url = _save_temp(image, "map_%s_%d" % (tower.key, self._frame))

        if index >= 0:
            entry = dict(self._map_history[index])
            entry["floor"] = floor_text
            if url:
                entry["url"] = url
            if grid:
                entry = self._merge_read_grid(entry, grid)
            self._map_history[index] = entry
        else:
            new_entry = {"id": entry_id, "floor": floor_text, "url": url,
                         "mons": [], "items": [], "grid": {}}
            self._map_history.insert(0, self._merge_read_grid(new_entry,
                                                             grid or {}))
        self.mapHistoryChanged.emit()
        self.statusTextChanged.emit()

    def _merge_read_grid(self, entry, grid) -> dict:
        """把这次读到的「每格有什么」并进这一层（刷新和「读地图」共用这一条规则）。

        规则（用户 2026-10-31）：
        - **用户手动定过的一个字段都不碰**：标的格子、改过的怪行/资源行、楼梯；
        - 其余按这次读到的重建：清单里的怪/资源都从格子里数出来，
          **数量 = 它占几格**（"AI 现在不需要读数量"，它数出来的经常是血量/效果值）；
        - 这次没读到、又不是用户定的东西就没了 —— AI 读的归 AI，不会越刷越多；
        - 楼梯并进（用户定过的保留，其余按这次读到的重来）。

        返回新的 entry（不改传入的那个 dict）。
        """
        new_cells = (grid or {}).get("cells") or []
        if not new_cells:
            # 这次一个格子都没读到：清单和坐标都别动 —— "没读到"不等于"图上没有"
            return dict(entry)
        old_cells = (entry.get("grid") or {}).get("cells") or []
        cells = merge_cells(old_cells, new_cells)
        # 怪名对到手册的写法；手册里没有的名字直接不记（用户："哪里来的绿头怪"）
        cells = _align_grid_names({"cells": cells},
                                  self._monsters).get("cells") or []
        cells = _drop_unknown_monsters(cells, self._monsters)

        updated = dict(entry)
        updated["mons"] = self._rows_from_cells(entry.get("mons"), cells,
                                                "monster")
        updated["items"] = self._rows_from_cells(entry.get("items"), cells,
                                                 "item")
        # 资源的"同一样东西"按图标身份认（红药水 / 红血瓶 是一瓶）：格子和清单
        # 两头都用同一份效果，`gridPositions` 才认得出"这一行标在哪几格"
        effect_of = {str(row.get("name") or ""): str(row.get("effect") or "")
                     for row in updated["items"]}
        for cell in cells:
            if str(cell.get("kind") or "") != "item" or is_manual(cell):
                continue
            name = str(cell.get("name") or "")
            if name in effect_of:
                cell["effect"] = effect_of[name]
        updated["grid"] = {"cells": cells}

        found = _stairs_from_grid(cells)
        if found:
            updated["stairs"] = _merge_stairs(_stairs_list(updated.get("stairs")),
                                              found)
        return updated

    def _rows_from_cells(self, old_rows, cells, kind) -> list:
        """清单行按格子重算：**用户定过的原样留着**，其余照这次格子里数出来的重建。

        `count` = 这个名字占了几格（AI 不再读数量）；这次一格都没有的旧行不留
        （它是 AI 读进来的，AI 这次没读到就说明读错了）。
        """
        from ....game import iteminfo

        def identity(name):
            """同一样东西怎么认：资源按图标身份（红药水/红血瓶 是一瓶），怪按名字。"""
            key = iteminfo.key_for(name) if kind == "item" else ""
            return ("item:" + key) if key else ("name:" + name)

        counts, first_name, order = {}, {}, []
        for cell in cells:
            if str(cell.get("kind") or "") != kind:
                continue
            name = str(cell.get("name") or "").strip()
            if not name:
                continue
            key = identity(name)
            if key not in counts:
                order.append(key)
                counts[key] = 0
                first_name[key] = name
            counts[key] += 1

        def build(name, count):
            if kind == "item":
                return self._fill_item_display({"name": name, "count": count,
                                                "effect": "", "icon": ""})
            return {"name": name, "count": count}

        rows, done = [], set()
        for row in old_rows or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            key = identity(name)
            if is_manual(row):
                rows.append(dict(row))
                done.add(key)
                continue
            if key in counts and key not in done:
                rows.append(build(first_name[key], counts[key]))
                done.add(key)
        for key in order:
            if key in done:
                continue
            rows.append(build(first_name[key], counts[key]))
            done.add(key)
        return rows

    @Slot(str, result=bool)
    def ensureFloor(self, floor_text) -> bool:
        """这一层还没有记录就建一条空的（楼梯通到"还没读过"的那层也切得过去）。

        用户："路线移到楼梯要换层！！！！" —— 只读到 1 层时，踩上楼梯没地方可切，
        看着就是"切层失败"。建一条空记录（无截图、无怪）就够了：地图那边显示
        "这一层还没有截图"，路线照样接着画。
        """
        floor_text = str(floor_text or "").strip()
        if not floor_text:
            return False
        if self._find_floor(floor_text) >= 0:
            return False
        self._map_history.insert(0, {"floor": floor_text, "url": "",
                                     "mons": [], "items": [],
                                     "grid": {"cells": []}, "routes": []})
        self.mapHistoryChanged.emit()
        return True

    @Slot(str)
    def removeFloor(self, floor_text) -> None:
        """删掉这一层的记录（读错层/不想要了）。

        「清空」只能清全部：读错一层时用户会想删掉那一条，而不是全清重读。
        """
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return
        entry = self._map_history.pop(position)
        self.mapHistoryChanged.emit()
        trace.note("manual.remove_floor", floor=floor_text,
                   mons=len(entry.get("mons") or []),
                   items=len(entry.get("items") or []))

    @Slot(str, str)
    def saveFloorMemo(self, floor_text, text) -> None:
        """给某一层记一句备忘（唯一会跨重启跟着 last_session.json 走的自由文本）。"""
        from .... import trace
        floor_text = str(floor_text or "")
        memo = str(text or "").replace("\r", " ").replace("\n", " ").strip()
        position = self._find_floor(floor_text)
        if position < 0:
            return
        entry = self._map_history[position]
        if str(entry.get("memo") or "") == memo:
            return
        updated = dict(entry)
        if memo:
            updated["memo"] = memo
        else:
            updated.pop("memo", None)
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
        trace.note("manual.floor_memo", floor=floor_text, memo=memo)

    # ---- 手动修改某层的资源（beta）：AI 读不准时自己改 ----

    @Slot(str)
    def refreshFloorCounts(self, floor_text) -> None:
        """某一层行尾的 ↻：重读这一层的「每个格子里有什么」，按它更新清单和坐标。

        怪和资源（宝石/血瓶/钥匙/金币/武器/防具）都从格子里数：**数量 = 占几格**
        （用户 2026-10-31："AI 现在不需要读数量"）。合并规则见 `_merge_read_grid`：
        用户手动定过的东西一个字段都不动。

        也不再要求这层先有怪：一层没加过怪、刚「读地图」建出来的，也能直接点。
        """
        from .... import trace
        floor_text = str(floor_text or "")
        label = floor_text or "这层"
        position = self._find_floor(floor_text)
        self._task_seq += 1
        task_id = self._task_seq
        started = time.time()
        if position < 0:
            # 以前这里静默 return：点 ↻ 像没反应，用户只会再点几次
            trace.note("scan.no_such_floor", floor=floor_text)
            self._tasks.insert(0, {
                "id": task_id, "state": "failed",
                "text": "统计失败：找不到「%s」这一层" % label,
                "started": started})
            del self._tasks[TASK_LIMIT:]
            self.tasksChanged.emit()
            return
        url = str(self._map_history[position].get("url") or "")
        if not url:
            self._tasks.insert(0, {
                "id": task_id, "state": "failed",
                "text": "统计失败：%s 还没有地图截图（先点「读地图」）" % label,
                "started": started})
            del self._tasks[TASK_LIMIT:]
            self.tasksChanged.emit()
            trace.note("scan.blocked", floor=floor_text, reason="no_shot")
            return
        # 这一行的缩略图 = 这一层已经有的那张截图（用户 2026-10-31：
        # "刷新的时候怎么也没缩略图" —— 以前这条任务没带 url，左边永远是空的）
        self._tasks.insert(0, {"id": task_id, "seq": self._map_seq,
                               "state": "running", "mode": "map",
                               "text": "读 %s 的地图…" % label,
                               "url": url,
                               "started": started})
        del self._tasks[TASK_LIMIT:]
        self.tasksChanged.emit()
        trace.note("scan.start", floor=floor_text,
                   known=len(self._monsters))
        self._start_scan_task(url, floor_text, task_id=task_id)

    def _get_counting_floor(self):
        return self._counting_floor

    @Slot()
    def clearMaps(self) -> None:
        """清空地图列表。

        界面上已经**没有入口**（「清空」按钮是 owner 要求删掉的）；留着是给测试和
        "整块重置"用 —— 「地图被清空时「这一层」弹窗要收起」这条行为就靠它触发。
        """
        if self._map_history:
            self._map_history.clear()
            self.mapHistoryChanged.emit()

    def _get_map_history(self):
        """地图记录（QML 直接画）。

        资源那几行在这里补齐"图标 + 效果"：图标按名字查（红血瓶→potion_red），
        效果按塔的道具表查（红宝石→攻击 +2）。用户明确要求效果**写死**，
        所以只要图标能对上，就以表里的为准，不把 AI 读到的错效果显示出来。
        （补的那套规则在 `_fill_item_display`，和「这一层」清单共用一份。）
        """
        out = []
        for entry in self._map_history:
            row = dict(entry)
            row["items"] = [self._fill_item_display(item)
                            for item in (entry.get("items") or [])
                            if isinstance(item, dict)]
            out.append(row)
        return out

    def _fill_item_display(self, item):
        """资源行的"图标 + 效果"一律以道具表为准（返回新 dict）。

        用户："地图我点刷新，怎么读进来的资源还是没有图标？" —— 刷新/读图
        （`_apply_scan` / `_attach_items`）只拿到名字和数量，图标和效果是空的；
        以前只有 `_get_map_history()`（主界面地图块）会补，而点开「这一层」清单
        走的是 `sortedSheetItems()`，空白就一直露在用户眼前。

        规则只有这一条，实现也只有这一处：
        - **图标**：名字 → 道具表（红血瓶=potion_red）优先，查不到才用行里存的
          （AI 裁的临时图 / 用户换过的）；临时图已经不在盘上的丢掉，别画破图；
        - **效果**：查得到就以表里的为准（用户要求写死），但行里打了
          `effect_manual` 的（他自己改过数值）不动。
        """
        from ....game import iteminfo
        copy = dict(item)
        by_name = iteminfo.icon_for(copy.get("name") or "")
        stem = by_name or str(copy.get("icon") or "").strip()
        if _dead_icon_file(stem):
            stem = ""
        if stem:
            copy["icon"] = stem
        if not copy.get("effect_manual"):
            fixed = iteminfo.effect_for(stem, copy.get("name") or "")
            if fixed:
                copy["effect"] = fixed
        return copy
