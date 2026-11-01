"""跨层：踩/点楼梯换层（**集成测试**，只走真事件）。

标准见 `tests/integration/README.md`。这一份只剩"用户能通过界面做成"的用例：
点按钮、点侧栏一行、在图上长按拖、往坐标格里粘字按回车。

**不符合标准、已经删掉的**（都在旧版本里，只调 QML 函数/Slot 或改私有数据来证明行为）：
  · `test_floors_are_ordered_by_the_number_in_the_name` —— 直调 `window.adjacentFloor()`
  · `test_floor_names_without_a_trailing_number_still_step_up` —— 同上
  · `test_a_floor_can_have_several_stairs_each_with_its_own_target` —— 直调
    `addStairRow/saveStair/setStairTarget`（同一条规则在单测 `test_stairs.py` 里）
  · `test_footer_says_the_stairs_are_not_marked` —— 断言的是界面文字，但触发靠直接改数据
  · `test_stepping_on_a_stair_goes_to_the_floor_it_points_at`、`test_a_stair_can_skip_floors`、
    `test_stair_without_a_target_still_switches_to_the_neighbour`、
    `test_a_stair_cell_from_the_map_read_also_switches`、
    `test_target_floor_without_the_back_stair_lands_on_the_same_cell`
    —— 全部直调 `window.routeEnterCell(layer, cell)`，没走鼠标

边界：真的 Controller + 真 QML + 真事件；桩掉抓图/AI；起点数据直接摆（读取链路不在本文件）。

每条用例的注释写两件事：**测什么** + **走过哪些界面**。
"""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from .... import helpers


def _make(stairs=None, floor="2层", floors=("1层", "2层", "3层")):
    """起真的 Controller + QML，摆好这一局的起点数据。"""
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "0"}
    history = []
    for name in floors:
        entry = {"floor": name, "url": "", "mons": [], "items": [],
                 "grid": {"cells": []}, "routes": []}
        if stairs and name in stairs:
            entry["stairs"] = stairs[name]
        history.append(entry)
    controller._map_history = history
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    window.selectFloor(floor)
    window.showMap()
    helpers.wait_for(lambda: helpers.find_item(window, "mapPanel") is not None)
    return controller, engine, window


def _layer(window):
    layer = helpers.find_item(window, "routeLayer")
    assert layer is not None
    assert helpers.wait_for(
        lambda: float(layer.property("cell") or 0) > 0, timeout=5.0), \
        "格子边长一直是 0，地图没摆好"
    return layer


def _point(layer, row, col):
    side = float(layer.property("cell"))
    return layer.mapToScene(QPointF((col + 0.5) * side, (row + 0.5) * side))


def _drag_onto(window, layer, start, steps):
    """真鼠标：按下 → 等长按起笔 → 一格一格移（只走正交相邻）→ 松手。"""
    target = helpers.window_of(window, layer)
    point = _point(layer, *start)
    helpers.APP.sendEvent(target, QMouseEvent(
        QEvent.MouseButtonPress, point, point, Qt.LeftButton, Qt.LeftButton,
        Qt.NoModifier))
    helpers.APP.processEvents()
    assert helpers.wait_for(lambda: layer.property("editing") is True,
                            timeout=2.0), "长按没把路线起起来"
    for row, col in steps:
        point = _point(layer, row, col)
        helpers.APP.sendEvent(target, QMouseEvent(
            QEvent.MouseMove, point, point, Qt.NoButton, Qt.LeftButton,
            Qt.NoModifier))
        helpers.APP.processEvents()
    helpers.APP.sendEvent(target, QMouseEvent(
        QEvent.MouseButtonRelease, point, point, Qt.LeftButton, Qt.NoButton,
        Qt.NoModifier))
    helpers.APP.processEvents()


def _inside(item, name):
    """清单每行都可能有同名子控件，必须在这一行里面找。"""
    stack = list(item.childItems())
    while stack:
        node = stack.pop()
        if node.objectName() == name and node.isVisible():
            return node
        stack.extend(node.childItems())
    return None


def _paste(window, field, text):
    """真操作：点开那一格 → 粘文本 → 回车（`window` = 那一格所在的那扇窗）。"""
    assert field is not None, "要粘的那一格没找到"
    helpers.click_item(window, field)
    helpers.APP.processEvents()
    editor = None
    for item in helpers.find_all(window, "coordEditor"):
        if item.isVisible():
            editor = item
    assert editor is not None, "点开之后没出现输入框"
    editor.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(editor.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def _routes(controller, floor_text):
    """这一层存下来的路线（公开 Slot，界面读的是同一份）。"""
    value = controller.routeCells(floor_text, 0)
    return value.toVariant() if hasattr(value, "toVariant") else list(value or [])


def test_rail_row_click_switches_the_map_to_that_floor():
    """测什么：侧栏一行一层，点哪行大图就换到哪层。

    交互顺序：① 点侧栏那一行 ② 断言大图换到那一层（`mapFloor`）。
    """
    controller, engine, window = _make(floors=("1层", "2层", "3层"), floor="2层")
    rows = helpers.find_all(window, "floorRailRow")
    assert len(rows) == 3
    helpers.click_item(window, rows[0])
    helpers.APP.processEvents()
    assert window.property("mapFloor") == "3层"


def test_long_press_drag_onto_a_stair_switches_and_lands_on_the_back_stair():
    """测什么：图上长按起笔，拖到楼梯格 → 切到那一行写的层，并落在目标层的回程楼梯上。

    交互顺序：① 在第 0 行第 11 列按下并按住 350ms 起笔 ② 往下拖一格（踩到楼梯）
    ③ 松手 → 断言 `mapFloor` 变 3层、存下来的路线末格落在 3层 (2,6)。
    """
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 11, "dir": "up", "to": "3层"}],
        "3层": [{"row": 2, "col": 6, "dir": "down", "to": "2层"}]})
    layer = _layer(window)
    _drag_onto(window, layer, (0, 11), [(1, 11)])

    assert window.property("mapFloor") == "3层"
    cells = _routes(controller, "2层")
    assert cells, "路线没存下来"
    assert (cells[-1]["floor"], cells[-1]["row"], cells[-1]["col"]) == \
        ("3层", 2, 6), "没落在目标层那个回程楼梯上"


def test_pasting_a_coordinate_into_the_row_sets_the_position():
    """测什么：「当前」坐标格点开粘 "2,4" → 楼梯位置定成第 2 行第 4 列，格子上带着层数。

    交互顺序：① 点「清单 ›」开这一层 ② 点「＋ 上楼梯」 ③ 点那一行的「当前」格
    ④ 粘「2,4」回车 → 断言楼梯位置是 (1,3)、格子上写着「2层 2,4」。
    """
    controller, engine, window = _make()
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True
    helpers.click_item(window, helpers.find_item(window, "floorAddStair"))
    helpers.APP.processEvents()

    row = helpers.find_all(window, "floorStairRow")[0]
    _paste(window, _inside(row, "floorStairPos"), "2,4")

    stairs = controller.stairsOf("2层")
    assert (stairs[0]["row"], stairs[0]["col"]) == (1, 3)
    labels = helpers.texts_of(helpers.find_item(window, "floorStairPos"))
    assert "2层 2,4" in labels


def test_pasting_a_coordinate_into_the_exit_field_sets_the_arrival():
    """测什么：「出口」格粘 "6,7" → 落点定成第 6 行第 7 列。

    交互顺序：① 点「清单 ›」开这一层 ② 点那一行的「出口」格 ③ 粘「6,7」回车
    → 断言落点是 (5,6)。
    """
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 3, "dir": "up", "to": "3层"}]})
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True

    row = helpers.find_all(window, "floorStairRow")[0]
    _paste(window, _inside(row, "floorStairArrive"), "6,7")

    stairs = controller.stairsOf("2层")
    assert (stairs[0]["toRow"], stairs[0]["toCol"]) == (5, 6)
