"""每层记录本身：建/删/改名、备忘、刷新入口、地图历史；资源行补图标和效果也在这儿。"""

import time

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...constants import MAP_HISTORY_LIMIT, TASK_LIMIT
from ...toolkit.pictures import _save_temp

from .common import _align_grid_names, _dead_icon_file


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
                entry["grid"] = _align_grid_names(grid, self._monsters)
            self._map_history[index] = entry
        else:
            self._map_history.insert(0, {"id": entry_id, "floor": floor_text,
                                         "url": url, "mons": here,
                                         "items": items or [],
                                         "grid": _align_grid_names(
                                             grid or {}, self._monsters)})
            del self._map_history[MAP_HISTORY_LIMIT:]
        self.mapHistoryChanged.emit()
        self.statusTextChanged.emit()

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
        self._tasks.insert(0, {"id": task_id, "seq": self._map_seq,
                               "state": "running",
                               "text": "读 %s 的地图…" % label,
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
