"""楼梯：一层有**好几个**，每个自己记得通到哪一层。

用户 2026-10-30 两次纠正：
  · "我设想的换层是将人物移动到楼梯才上层或下层"（踩楼梯换层）
  · "谁告诉你一层只有一个上楼或下楼的？谁告诉你0层就一定去1层的？"

所以数据是一张**列表**，一行一个楼梯：

    entry["stairs"] = [{"row": 2, "col": 11, "dir": "up", "to": "通天塔3"}, ...]

- `dir` 只有 up / down（只用来画箭头、排顺序）；
- `to` 是**这一格通到哪一层**，跟层号顺序无关（0 层可以直接通 5 层）；
  `to` 空串 = 还没选目标层；
- `row/col` 是 0 开始、13×13 以内；`-1` = 还没标位置（刚加的行）。

老记录里是 `{"up": {...}, "down": {...}}` 那种"一层两个"的写法，读的时候
（`_stairs_list`）自动转成列表，不用用户重标。
"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from .grid import _cell_key, _in_range

# 方向：只影响画箭头，不影响去哪一层
DIRECTIONS = ("up", "down")


def _clean_stair(item) -> dict:
    """一行楼梯；坐标/方向不合法就 None（-1 = 还没标位置，合法）。"""
    if not isinstance(item, dict):
        return None
    direction = str(item.get("dir") or "").strip().lower()
    if direction not in DIRECTIONS:
        return None
    try:
        row = int(item.get("row"))
        col = int(item.get("col"))
    except (TypeError, ValueError):
        return None
    if row >= 0 and col >= 0:
        if not _in_range((row, col)):
            return None
    else:
        row, col = -1, -1               # 没标位置 / 标到界外：当没标
    # 落点：通到那一层时落在哪一格（-1 = 还没指）
    try:
        to_row = int(item.get("toRow", -1))
        to_col = int(item.get("toCol", -1))
    except (TypeError, ValueError):
        to_row, to_col = -1, -1
    if to_row < 0 or to_col < 0 or not _in_range((to_row, to_col)):
        to_row, to_col = -1, -1
    return {"row": row, "col": col, "dir": direction,
            "to": str(item.get("to") or "").strip(),
            "toRow": to_row, "toCol": to_col}


def _stairs_list(raw) -> list:
    """这一层所有楼梯（列表）；老的"一层两个"写法自动转换。"""
    if isinstance(raw, dict):
        out = []
        for direction in DIRECTIONS:
            cell = raw.get(direction)
            if isinstance(cell, dict):
                one = _clean_stair(dict(cell, dir=direction))
                if one:
                    out.append(one)
        return out
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        one = _clean_stair(item)
        if one:
            out.append(one)
    return out


class StairsMixin:
    @Slot(str, result="QVariantList")
    def stairsOf(self, floor_text) -> list:
        """这一层的楼梯：`[{row, col, dir, to}]`（`row = -1` = 还没标位置）。"""
        position = self._find_floor(floor_text)
        if position < 0:
            return []
        return _stairs_list(self._map_history[position].get("stairs"))

    @Slot(str, str, result=int)
    def addStair(self, floor_text, direction="up") -> int:
        """加一行楼梯（位置还没标、目标层还没选），返回它的序号。"""
        direction = str(direction or "up").strip().lower()
        if direction not in DIRECTIONS:
            direction = "up"
        position = self._find_floor(floor_text)
        if position < 0:
            return -1
        entry = dict(self._map_history[position])
        stairs = _stairs_list(entry.get("stairs"))
        stairs.append({"row": -1, "col": -1, "dir": direction, "to": ""})
        entry["stairs"] = stairs
        self._map_history[position] = entry
        self.mapHistoryChanged.emit()
        return len(stairs) - 1

    # ---- 改某一行楼梯：**规则只有这一份**（下面几个槽都是它的薄包装）----
    def _change_stair(self, floor_text, index, **fields) -> bool:
        position = self._find_floor(floor_text)
        if position < 0:
            return False
        entry = dict(self._map_history[position])
        stairs = _stairs_list(entry.get("stairs"))
        if index < 0 or index >= len(stairs):
            return False
        one = dict(stairs[int(index)])
        one.update(fields)
        cleaned = _clean_stair(one)
        if cleaned is None:
            return False
        stairs[int(index)] = cleaned
        entry["stairs"] = stairs
        self._map_history[position] = entry
        self.mapHistoryChanged.emit()
        return True

    @Slot(str, int, int, int, result=bool)
    def saveStair(self, floor_text, index, row, col) -> bool:
        """把第 index 个楼梯的位置定在 (row, col)。"""
        return self._change_stair(floor_text, index, row=int(row), col=int(col))

    @Slot(str, int, str, result=bool)
    def setStairTarget(self, floor_text, index, target) -> bool:
        """第 index 个楼梯通到哪一层（空串 = 还没选）。"""
        return self._change_stair(floor_text, index,
                                  to=str(target or "").strip())

    @Slot(str, int, int, int, result=bool)
    def setStairArrival(self, floor_text, index, row, col) -> bool:
        """落点：通到目标层以后，落在那一层的哪一格。"""
        return self._change_stair(floor_text, index,
                                  toRow=int(row), toCol=int(col))

    @Slot(str, int, int, int, str, result=bool)
    def setStairArrivalWithTarget(self, floor_text, index, row, col,
                                 target="") -> bool:
        """落点 + "通到哪一层"**一次改完**。

        界面那边粘一个带层数的坐标（"3层 6,7"）要同时改这两样；分两次调的话
        第一次就发信号重建了这一行，第二次拿到的是已经销毁的委托
        （实测：`ReferenceError: host is not defined`）。
        """
        return self._change_stair(floor_text, index, toRow=int(row),
                                  toCol=int(col),
                                  to=str(target or "").strip())

    @Slot(str, int, str, result=bool)
    def setStairDirection(self, floor_text, index, direction) -> bool:
        """改第 index 行的方向（上/下）—— AI 认错方向时自己点一下换过来。"""
        direction = str(direction or "").strip().lower()
        if direction not in DIRECTIONS:
            return False
        return self._change_stair(floor_text, index, dir=direction)

    @Slot(str, int, result=bool)
    def removeStair(self, floor_text, index) -> bool:
        """删掉第 index 行楼梯（标错了 / 不需要）。"""
        position = self._find_floor(floor_text)
        if position < 0:
            return False
        entry = dict(self._map_history[position])
        stairs = _stairs_list(entry.get("stairs"))
        if index < 0 or index >= len(stairs):
            return False
        stairs.pop(int(index))
        if stairs:
            entry["stairs"] = stairs
        else:
            entry.pop("stairs", None)
        self._map_history[position] = entry
        self.mapHistoryChanged.emit()
        return True
