"""格子编辑的**拖放**集成测试：真的把格子拖到词条行上。

为什么单独一个文件：多选落格那段代码写在 `FloorSheetWindow.qml` 的
`DropArea.onDropped` 里，直接调 `gridAssignMany` 是绕过它的 —— 以前就是这么漏的
（只落了第一格：落第一格时那一行词条被重建，循环里再读名字拿到 null，
用户："编辑模式多选添加有问题"）。这里合成 enter/move/drop 打到真的 DropArea 上。

真值：拖 N 格 = N 格都记给这个词条、数量 = N、资源带自己的 effect、落完清勾选。
"""

from .... import helpers


def _sheet(mons=None, items=None):
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": mons or [{"name": "血蚊", "count": 0},
                         {"name": "绿水母", "count": 0}],
        "items": items or [],
        "grid": {"cells": []}}]
    window.setProperty("floorWindows", ["长安1"])
    helpers.APP.processEvents()
    sheet = window.floorSheetOf("长安1")
    helpers.APP.processEvents()
    window.gridEditToggle("长安1")
    helpers.APP.processEvents()
    return controller, engine, window, sheet


def _row(window, name, index=0):
    rows = [item for item in helpers.find_all(window, name) if item.isVisible()]
    assert len(rows) > index, f"没找到第 {index} 行 {name}"
    return rows[index]


def _cells(window):
    value = window.property("gridMulti")
    return value.toVariant() if hasattr(value, "toVariant") else value


def test_drop_multi_cells_on_monster_row_lands_every_cell():
    controller, engine, window, sheet = _sheet()
    for cell in ((0, 0), (1, 1), (2, 2)):
        window.gridMultiToggle(*cell)
    helpers.drop_cells(window, _row(window, "floorMonRow"),
                       {"cells": [{"row": 0, "col": 0},
                                  {"row": 1, "col": 1},
                                  {"row": 2, "col": 2}]})

    assert controller._map_history[0]["grid"]["cells"] == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 1, "col": 1, "kind": "monster", "name": "血蚊"},
        {"row": 2, "col": 2, "kind": "monster", "name": "血蚊"}]
    assert controller._map_history[0]["mons"][0]["count"] == 3
    # 落完就清掉勾选，别留到下一次
    assert _cells(window) == []


def test_drop_single_cell_payload_still_works():
    """没多选时拖一格：载荷还是 `{row, col}`，走的也是这条路。"""
    controller, engine, window, sheet = _sheet(
        mons=[{"name": "血蚊", "count": 0}, {"name": "绿水母", "count": 0}])
    helpers.drop_cells(window, _row(window, "floorMonRow", 1),
                       {"row": 9, "col": 9})

    assert controller._map_history[0]["grid"]["cells"] == [
        {"row": 9, "col": 9, "kind": "monster", "name": "绿水母"}]
    mons = {m["name"]: m["count"] for m in controller._map_history[0]["mons"]}
    assert mons == {"血蚊": 0, "绿水母": 1}


def test_drop_multi_cells_on_item_row_keeps_effect():
    controller, engine, window, sheet = _sheet(items=[
        {"name": "血瓶", "effect": "体力 +150", "count": 0,
         "icon": "potion_red"}])
    for cell in ((5, 5), (6, 6)):
        window.gridMultiToggle(*cell)
    helpers.drop_cells(window, _row(window, "floorItemRow"),
                       {"cells": [{"row": 5, "col": 5},
                                  {"row": 6, "col": 6}]})

    assert controller._map_history[0]["grid"]["cells"] == [
        {"row": 5, "col": 5, "kind": "item", "name": "血瓶",
         "effect": "体力 +150"},
        {"row": 6, "col": 6, "kind": "item", "name": "血瓶",
         "effect": "体力 +150"}]
    assert controller._map_history[0]["items"][0]["count"] == 2
    assert _cells(window) == []

