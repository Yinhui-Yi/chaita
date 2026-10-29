"""格子编辑：编辑模式下把地图上的坐标拖到怪/资源词条上，纠正 AI 读错的格子。

用户："读出来一大半都是错的……编辑模式地图上要覆盖坐标系……长按拖到下方某一
词条上要将该坐标记录给词条……编辑结束修改你的 json"。

格子记录就是 `entry["grid"]["cells"]`（`[{row, col, kind, name}]`，0 开始），
和 `agent.map.read` 的 `CELL_KINDS` 一致：只记怪 / 宝石 / 血瓶。拖一个坐标到
词条上 = 把那一格改成这个词条（一格只留一样，旧的被顶掉）；拖到空名 = 清掉。

一批坐标（Ctrl 多选）走同一个入口 `assignGridCells`：一次改完、只发一次
`mapHistoryChanged`。
"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

# 一格能记的两类东西（和 agent.map.read.CELL_KINDS 同一份规则）
CELL_KINDS = ("monster", "item")
# 地图固定 13×13（和 agent.map.read.SIDE 同一份规则）：出界的坐标一律不算格子
SIDE = 13


def _cell_key(cell):
    """(row, col)；不是合法坐标就 None（脏数据不该让整次落格失败）。"""
    if not isinstance(cell, dict):
        return None
    try:
        return int(cell.get("row")), int(cell.get("col"))
    except (TypeError, ValueError):
        return None


def _in_range(key) -> bool:
    """这一格在地图里吗（0..SIDE-1）。出界的坐标没有任何意义。"""
    return (key is not None
            and 0 <= key[0] < SIDE and 0 <= key[1] < SIDE)


class GridMixin:
    @Slot(str, result="QVariantList")
    def gridCells(self, floor_text) -> list:
        """这一层 `grid` 里的每个格子：`[{row, col, kind, name}]`（0 开始）。

        出界的脏格不返回（画也画不到，见 `_in_range`）。
        """
        position = self._find_floor(floor_text)
        if position < 0:
            return []
        grid = self._map_history[position].get("grid") or {}
        return [dict(cell) for cell in (grid.get("cells") or [])
                if isinstance(cell, dict) and _in_range(_cell_key(cell))]

    @Slot(str, "QVariantList", str, str, result=bool)
    @Slot(str, "QVariantList", str, str, str, result=bool)
    def assignGridCells(self, floor_text, cells, kind, name, effect="") -> bool:
        """把 cells 里每个 (row, col) 一起记成 kind/name（资源再带 effect）。

        多选拖拽走这里，**一次只发一次 `mapHistoryChanged`**：那一层的怪/资源
        列表 model 就挂在 `mapHistory` 上，一格发一次会让持有拖放区的那个词条行
        在循环中途被重建，后面的格子读成空名字、又被当成"清掉"（用户："编辑模式
        多选添加有问题"）。name 空 = 把这些格子全清掉。

        顺手把**出界的脏格**（`row=20` 这种，以前没卡边界时拖出来的）扔掉：
        它们在图上点不到、也就永远删不掉（用户："为什么不能删坐标"），
        下一次任意落格就自愈。
        """
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return False
        kind = str(kind or "").strip()
        name = str(name or "").strip()
        wanted = [key for key in dict.fromkeys(
                      _cell_key(cell) for cell in (cells or []))
                  if _in_range(key)]
        if not wanted:
            return False
        entry = dict(self._map_history[position])
        grid = dict(entry.get("grid") or {})
        old_cells = [dict(cell) for cell in (grid.get("cells") or [])
                     if isinstance(cell, dict)]
        # 一格只留一样：先把这些坐标上的旧记录拿掉，记住原来挂的是谁
        targets = set(wanted)
        old_names = {str(cell.get("name") or "") for cell in old_cells
                     if _cell_key(cell) in targets}
        kept = [cell for cell in old_cells
                if _in_range(_cell_key(cell)) and _cell_key(cell) not in targets]
        kept_names = {str(cell.get("name") or "") for cell in old_cells
                      if not _in_range(_cell_key(cell))}
        if name and kind in CELL_KINDS:
            for row, col in wanted:
                cell = {"row": row, "col": col, "kind": kind, "name": name}
                if kind == "item":
                    cell["effect"] = str(effect or "")
                kept.append(cell)
        grid["cells"] = kept
        entry["grid"] = grid
        # 数量跟着位置走：被顶掉的、被扔掉的脏格、新挂上的，都重算一遍
        for affected in (old_names | kept_names | ({name} if name else set())):
            if affected:
                self._resync_count(entry, affected)
        self._map_history[position] = entry
        self.mapHistoryChanged.emit()
        trace.note("manual.assign_grid_cell", floor=floor_text,
                   cells=len(wanted), kind=kind, name=name, effect=effect)
        return True

    @Slot(str, int, int, str, str, result=bool)
    @Slot(str, int, int, str, str, str, result=bool)
    def assignGridCell(self, floor_text, row, col, kind, name,
                       effect="") -> bool:
        """单格版（拖一格 / 清一格）：规则只在 `assignGridCells` 里写一份。"""
        return self.assignGridCells(floor_text, [{"row": row, "col": col}],
                                    kind, name, effect)

    def _resync_count(self, entry, name) -> None:
        """把某个怪/资源的数量改成它在 grid 里出现的格数（0 = 一格都没标）。

        资源按"名字 + 效果"认：同名不同效果的（血瓶150 / 血瓶300）各数各的。
        出界的脏格不数 —— 图上根本不显示它，数量却跟着涨就对不上了。
        """
        cells = (entry.get("grid") or {}).get("cells") or []
        inside = [cell for cell in cells
                  if isinstance(cell, dict) and _in_range(_cell_key(cell))]
        for key in ("mons", "items"):
            rows = [dict(row) for row in (entry.get(key) or [])
                    if isinstance(row, dict)]
            if not any(str(row.get("name") or "") == name for row in rows):
                continue
            for row in rows:
                if str(row.get("name") or "") != name:
                    continue
                want = str(row.get("effect") or "")
                row["count"] = sum(
                    1 for cell in inside
                    if str(cell.get("name") or "") == name
                    and str(cell.get("effect") or "") == want)
            entry[key] = rows

    @Slot(str, str, result="QVariantList")
    @Slot(str, str, str, result="QVariantList")
    def gridPositions(self, floor_text, name, effect="") -> list:
        """这个怪/资源出现在哪些格（编辑模式给词条标"出现的位置"用）。

        资源按"名字 + 效果"认：两个同名血瓶各标各的，不再互相串。
        出界的脏格不返回：图上点不到的坐标不该出现在词条行里。
        """
        position = self._find_floor(floor_text)
        if position < 0:
            return []
        name = str(name or "").strip()
        effect = str(effect or "")
        cells = ((self._map_history[position].get("grid") or {})
                 .get("cells") or [])
        return [{"row": int(cell.get("row")), "col": int(cell.get("col"))}
                for cell in cells
                if isinstance(cell, dict)
                and _in_range(_cell_key(cell))
                and str(cell.get("name") or "") == name
                and str(cell.get("effect") or "") == effect]
