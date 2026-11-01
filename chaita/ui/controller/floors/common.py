"""这一摊共用的小东西：icon 文件还在不在、格子坐标/合并规则、地图格子的怪名归一。"""

import os

# 用户手动定过的东西（格子 / 怪行 / 资源行 / 楼梯）都打这个标记：
# AI 再读一次时**一个字段都不许碰它**（用户 2026-10-31："手动修改过的词条你不要动"）。
MANUAL = "manual"


def _cell_key(cell):
    """`(row, col)`；不是合法坐标就 None（脏数据不该让整次落格失败）。"""
    if not isinstance(cell, dict):
        return None
    try:
        return int(cell.get("row")), int(cell.get("col"))
    except (TypeError, ValueError):
        return None


def is_manual(row) -> bool:
    """这条记录（格子/行/楼梯）是不是用户手动定过的。"""
    return isinstance(row, dict) and bool(row.get(MANUAL))


def mark_manual(row):
    """就地打上"用户定过的"标记，返回它本身（方便链式用）。"""
    if isinstance(row, dict):
        row[MANUAL] = True
    return row


def merge_cells(old_cells, new_cells) -> list:
    """把这次读到「每格有什么」并进这一层，返回合并后的格子。

    规则（用户 2026-10-31）：
    - **用户标的格子原样保留**，同一格以用户的为准（他拖的坐标是核过的，
      AI 读错才是常态 —— 编辑模式就是为纠正它而存在的）；
    - 其余格子按这次 AI 的**重来**：不是"只补空格"，因为模型每次读的位置会漂，
      只补不改会越刷越多（用户："我二次刷新时，地图的怪和资源会累计"）。
    """
    manual, taken = [], set()
    for cell in old_cells or []:
        if not is_manual(cell):
            continue
        key = _cell_key(cell)
        if key is None or key in taken:
            continue
        taken.add(key)
        manual.append(dict(cell))
    fresh = []
    for cell in new_cells or []:
        if not isinstance(cell, dict):
            continue
        key = _cell_key(cell)
        if key is None or key in taken:
            continue
        taken.add(key)
        fresh.append(dict(cell))
    return manual + fresh


def _dead_icon_file(text: str) -> bool:
    """这个 icon 指向的文件还在不在。

    AI 读画面时裁的图标存在 Temp（`.../chaita/<时间>_item_1.png`），重启/清理就
    没了；界面上再画就是一张打不开的图（用户："资源的缩略图怎么没有了"）。
    """
    value = str(text or "").strip()
    if not value:
        return False
    if value.startswith("file:"):
        from PySide6.QtCore import QUrl
        path = QUrl(value).toLocalFile()
    elif os.path.isabs(value):
        path = value
    else:
        return False        # 素材名（potion_red）不是文件，交给 QML 拼目录
    return not os.path.exists(path)


def _drop_unknown_monsters(cells, monsters) -> list:
    """手册里已经有怪名时，**格子里对不上任何一个手册名的怪不记**。

    地图上没字，模型是看图案猜的；手册读到真名以后，"绿头怪 / 红头怪"这种不属于
    这座塔的名字不该进记录（用户："哪里来的绿头怪、红头怪"）。用户标的格子一律不动；
    手册还没读到名字（`monsters` 空）时不筛 —— 那时候没东西可对。
    """
    from ....game import monster_names
    known = [str((row or {}).get("name") or "").strip()
             for row in monsters or [] if isinstance(row, dict)]
    known = [name for name in known if name]
    if not known:
        return list(cells or [])
    out = []
    for cell in cells or []:
        if not isinstance(cell, dict) or is_manual(cell):
            out.append(cell)
            continue
        if str(cell.get("kind") or "") != "monster":
            out.append(cell)
            continue
        name = str(cell.get("name") or "").strip()
        if not name:
            continue
        _mapping, unmatched, _invented = monster_names.align([name], known)
        if unmatched:
            continue
        out.append(cell)
    return out


def _align_grid_names(grid, monsters) -> dict:
    """把"每格有什么"里的**怪名**对到手册的写法（资源名不动，用户标的格子不动）。

    为什么：地图上没字，模型是看图案猜名字的（"红眼白猫"这种）。手册里的真名是
    "红头怪"，对不上就查不到数值/技能 —— 路线链那一格只能空着名字，算不出掉血。
    这里和这一层的怪清单用**同一套**归一规则（`monster_names.align`）。
    """
    from ....game import monster_names
    known = [str((row or {}).get("name") or "").strip()
             for row in monsters or [] if isinstance(row, dict)]
    known = [name for name in known if name]
    out = dict(grid or {})
    if not known:
        return out
    cells = []
    for cell in out.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        row = dict(cell)
        name = str(row.get("name") or "").strip()
        # 用户标的格子一个字段都不动（名字他也可能自己改过）
        if row.get("kind") == "monster" and name and not is_manual(row):
            mapping, _unmatched, _invented = monster_names.align([name], known)
            row["name"] = mapping.get(name, name)
        cells.append(row)
    out["cells"] = cells
    return out
