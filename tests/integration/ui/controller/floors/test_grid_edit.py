"""格子编辑集成测试：编辑模式下把坐标拖到词条上 → 落进那一层的 grid，数量跟着位置走。

链是 QML `gridAssign`（门面）→ `controller.assignGridCell` → `_resync_count`
→ 层记录。期望值从规则手写：一格只留一样；同名怪的数量 = 它在 grid 里的格数；
**同名资源按"名字+效果"认**（两个血瓶 150 / 300 各标各的，不互相串）。
"""

from .... import helpers


def _edit(items=None):
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": [{"name": "血蚊", "count": 1}],
        "items": items or [],
        "grid": {"cells": []}}]
    window.setProperty("gridEditOn", True)
    window.setProperty("gridEditFloor", "长安1")
    return controller, engine, window


def test_grid_edit_assigns_cell_and_resyncs_count():
    controller, engine, window = _edit()
    window.gridAssign(0, 0, "monster", "血蚊", "")
    window.gridAssign(0, 1, "monster", "血蚊", "")
    helpers.APP.processEvents()
    entry = controller._map_history[0]
    assert entry["grid"]["cells"] == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 0, "col": 1, "kind": "monster", "name": "血蚊"}]
    # 数量 = 出现的格数（两格 → 2）
    assert entry["mons"][0]["count"] == 2


def test_grid_edit_clear_removes_cell_and_zeroes_count():
    controller, engine, window = _edit()
    window.gridAssign(0, 0, "monster", "血蚊", "")
    window.gridAssign(0, 0, "", "", "")
    helpers.APP.processEvents()
    entry = controller._map_history[0]
    assert entry["grid"]["cells"] == []
    # 一格都不标了 → 数量归零
    assert entry["mons"][0]["count"] == 0


def test_two_same_name_items_get_separate_positions():
    controller, engine, window = _edit(items=[
        {"name": "血瓶", "effect": "体力 +150", "count": 1,
         "icon": "potion_red"},
        {"name": "血瓶", "effect": "体力 +300", "count": 1,
         "icon": "potion_red"}])
    # 第一个血瓶标 (0,0)，第二个血瓶标 (0,1)
    window.gridAssign(0, 0, "item", "血瓶", "体力 +150")
    window.gridAssign(0, 1, "item", "血瓶", "体力 +300")
    helpers.APP.processEvents()

    # 各查各的坐标，不再互相继承
    assert controller.gridPositions("长安1", "血瓶", "体力 +150") == [
        {"row": 0, "col": 0}]
    assert controller.gridPositions("长安1", "血瓶", "体力 +300") == [
        {"row": 0, "col": 1}]
    # 数量各算各的格数
    by_effect = {i["effect"]: i["count"]
                 for i in controller._map_history[0]["items"]}
    assert by_effect["体力 +150"] == 1
    assert by_effect["体力 +300"] == 1


def test_closing_floor_sheet_exits_grid_edit():
    controller, engine, window = helpers.make_controller()
    window.setProperty("gridEditOn", True)
    window.setProperty("gridEditFloor", "长安1")
    window.setProperty("floorWindows", ["长安1"])

    window.closeFloorSheet("长安1")
    helpers.APP.processEvents()

    assert window.property("gridEditOn") is False
    assert window.property("gridEditFloor") == ""
