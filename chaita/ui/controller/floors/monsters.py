"""这一层的怪：加一只、改名字/数量、删、勾掉打过了。"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...toolkit.library import _import_icon
from ...toolkit.texts import _carry_row


class FloorMonstersMixin:
    @Slot(str, str, result=int)
    def addFloorMonster(self, floor_text, name) -> int:
        """给这一层加一只怪，返回它在列表里的位置（-1 表示没加成）。"""
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return -1
        entry = dict(self._map_history[position])
        mons = list(entry.get("mons") or [])
        item = {"name": (name or "怪物").strip() or "怪物", "count": None}
        mons.append(item)
        mons.sort(key=lambda one: one["name"])
        entry["mons"] = mons
        self._map_history[position] = entry
        self.mapHistoryChanged.emit()
        trace.note("manual.add_floor_monster", floor=floor_text,
                   name=name, total=len(mons))
        return mons.index(item)

    @Slot(str, str, str, str, result=int)
    def addFloorMonsterFull(self, floor_text, name, count, icon_file="") -> int:
        """一次性加一只怪（连数量），返回它在列表里的位置。

        「这一层」的草稿保存只调这一个：以前是先 add 再 save，两次调用之间
        Repeater 已经把草稿组件销毁，第二次调用和收尾语句都不执行了
        （实测：数量加上了，编辑框关不掉）。
        """
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return -1
        clean = (name or "").strip()
        if not clean:
            return -1
        entry = dict(self._map_history[position])
        mons = list(entry.get("mons") or [])
        digits = "".join(ch for ch in (count or "") if ch.isdigit())
        item = {"name": clean, "count": int(digits) if digits else None}
        picked = _import_icon(icon_file, "floor")
        if picked:
            item["icon"] = picked
        mons.append(item)
        mons.sort(key=lambda one: one["name"])
        entry["mons"] = mons
        self._map_history[position] = entry
        self.mapHistoryChanged.emit()
        trace.note("manual.add_floor_monster", floor=floor_text, name=clean,
                   count=count, total=len(mons))
        return mons.index(item)

    @Slot(str, int)
    def removeFloorMonster(self, floor_text, index) -> None:
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return
        entry = dict(self._map_history[position])
        mons = list(entry.get("mons") or [])
        removed = ""
        if 0 <= index < len(mons):
            removed = str((mons.pop(index) or {}).get("name") or "")
        entry["mons"] = mons
        # 顺手把这只怪在这一层标过的格子清掉：坐标是按**名字**记的，不清的话
        # 删了再加一只同名的，旧坐标又回来了（用户 2026-10-31：
        # "我把怪删了重加为什么不是全新的"）。
        if removed:
            grid = dict(entry.get("grid") or {})
            cells = list(grid.get("cells") or [])
            keep = [cell for cell in cells
                    if not (str(cell.get("kind") or "") == "monster"
                            and str(cell.get("name") or "") == removed)]
            if len(keep) != len(cells):
                grid["cells"] = keep
                entry["grid"] = grid
        self._map_history[position] = entry
        self.mapHistoryChanged.emit()
        trace.note("manual.remove_floor_monster", floor=floor_text,
                   index=index, name=removed)

    @Slot(str, int, str, str)
    def saveFloorMonsterField(self, floor_text, index, field, text) -> None:
        """只改本层某只怪的一个字段（名字 / 数量），改完立刻落库。

        用户："点怪物直接就修改所有了？只需要点数字修改数量" —— 所以数量是行里的
        一个小输入框，点它改它，不再弹整行编辑。
        """
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return
        updated = dict(self._map_history[position])
        mons = [dict(mon) for mon in (updated.get("mons") or [])]
        if not (0 <= index < len(mons)):
            return
        value = (text or "").strip()
        if field == "name":
            if value == "":
                mons.pop(index)
                updated["mons"] = mons
                self._map_history[position] = updated
                self.mapHistoryChanged.emit()
                trace.note("manual.remove_floor_monster", floor=floor_text,
                           index=index, why="name_cleared")
                return
            mons[index]["name"] = value
        elif field == "count":
            digits = "".join(ch for ch in value if ch.isdigit())
            mons[index]["count"] = int(digits) if digits else None
        else:
            return
        updated["mons"] = mons
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
        self._mark_saved("mon", floor_text, index)
        trace.note("manual.floor_monster_field", floor=floor_text, index=index,
                   field=field, value=value)

    @Slot(str, int)
    def toggleFloorMonsterDone(self, floor_text, index) -> None:
        """这只怪打过了 / 撤销。"""
        self._toggle_done(floor_text, index, "mons")
