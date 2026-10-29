"""这一摊共用的小东西：判断一个 icon 指向的文件还在不在、地图格子的怪名归一。"""

import os


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


def _align_grid_names(grid, monsters) -> dict:
    """把"每格有什么"里的**怪名**对到手册的写法（资源名不动）。

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
        if row.get("kind") == "monster" and name:
            mapping, _unmatched, _invented = monster_names.align([name], known)
            row["name"] = mapping.get(name, name)
        cells.append(row)
    out["cells"] = cells
    return out
