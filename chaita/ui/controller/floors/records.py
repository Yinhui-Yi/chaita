"""每层记录本身：建/删/改名、备忘、刷新入口、地图历史；资源行补图标和效果也在这儿。"""

import time

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...constants import TASK_LIMIT
from ...toolkit.pictures import _save_temp

from .common import _align_grid_names, _dead_icon_file
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
    """AI 读到的楼梯并进已有的：同一个格子保留用户选过的目标层。"""
    merged = [dict(one) for one in (old or [])]
    for fresh in from_grid or []:
        hit = None
        for one in merged:
            if (int(one.get("row", -1)) == fresh["row"]
                    and int(one.get("col", -1)) == fresh["col"]):
                hit = one
                break
        if hit is None:
            merged.append(dict(fresh))
    return merged


class RecordsMixin:
    def _find_floor(self, floor_text):
        for position, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                return position
        return -1

    def _store_map_entry(self, tower, result, entry_id, floor_text, here,
                         items=None, quick_map=None, grid=None) -> None:
        """把这次的地图落到层数相同的那条记录上（没有就插一条）。

        grid = 每个格子里有什么（`docs/ROUTE.md` 的路线链按它预填）；
        这次没读到就保留那条记录上原来的，别把已经读到的清掉。
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
            # 这次没读到怪/资源时**不要清空那层已有的记录**：
            # 「读地图」只更新层数和截图，之前加的怪、勾过的状态都得留着
            if here:
                entry["mons"] = here
            if items:
                entry["items"] = items
            if url:
                entry["url"] = url
            if grid:
                aligned = _align_grid_names(grid, self._monsters)
                entry["grid"] = aligned
                # 读地图顺带读到的楼梯：并进这一层（同格保留用户选过的目标层）
                found = _stairs_from_grid(aligned.get("cells") or [])
                if found:
                    entry["stairs"] = _merge_stairs(
                        _stairs_list(entry.get("stairs")), found)
            self._map_history[index] = entry
        else:
            aligned = _align_grid_names(grid or {}, self._monsters)
            new_entry = {"id": entry_id, "floor": floor_text,
                         "url": url, "mons": here,
                         "items": items or [], "grid": aligned}
            found = _stairs_from_grid(aligned.get("cells") or [])
            if found:
                new_entry["stairs"] = _merge_stairs([], found)
            self._map_history.insert(0, new_entry)
        self.mapHistoryChanged.emit()
        self.statusTextChanged.emit()

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
        """某一层行尾的 ↻：读这一层的地图，把"有哪些怪、各几只"和
        **"有哪些资源（血瓶/宝石/钥匙/金币）、各几个"**一起读出来写进去。

        以前只读怪，资源永远停在旧值（用户："刷新地图的时候没有更新资源
        包括宝石血瓶钥匙等"）。现在一次会话两边都问（`read_floor_map`）。

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
