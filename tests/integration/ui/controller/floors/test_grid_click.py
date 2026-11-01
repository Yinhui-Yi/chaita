"""格子编辑的单击 / 右键（**集成测试**，真鼠标事件打到地图上）。

用户 2026-10-30 定的规矩：
· **左键单击 = 选中这一格**（不再"一步删坐标"）；
· **右键 = 出小窗**，可以「复制坐标」/「清掉这一格」；
· 13×13 之外不算格子：不悬停、不选（以前能拖出第 21 行）。

标准见 `tests/integration/README.md`。驱动：点侧栏行选层 → 点「编辑」进编辑模式 →
在大图上真发鼠标按下/抬起/移动。断言读公开属性（`window.gridPicked / gridHover`、
`controller.gridCells(floor)`、菜单和剪贴板）。

**删掉的 1 条**：`test_cell_at_outside_13x13_is_empty` —— 它直接调 `layer.cellAt(x, y)`
问"这一格算不算"（纯函数，一次鼠标都没发），属于单测范畴；出界这件事在
`test_press_outside_13x13_does_nothing` 里用真事件覆盖。
"""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from .... import helpers


def _edit(cells=None):
    """起一套窗口：摆好这一层的格子，再用界面动作进编辑模式。"""
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": [{"name": "血蚊", "count": 0},
                 {"name": "绿水母", "count": 0}],
        "items": [],
        "grid": {"cells": cells or []},
        "routes": []}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    # 用户动作：点侧栏那一行选层 → 点「编辑」
    assert helpers.wait_for(
        lambda: helpers.find_item(window, "floorRailRow") is not None), \
        "地图那一栏没出来"
    helpers.click_item(window, helpers.find_all(window, "floorRailRow")[0])
    helpers.APP.processEvents()
    helpers.click_item(window, helpers.find_item(window, "mapGridEdit"))
    helpers.APP.processEvents()
    assert window.property("gridEditOn") is True, "「编辑」没进编辑模式"
    assert helpers.wait_for(
        lambda: helpers.find_item(window, "gridLayer") is not None), \
        "格子层没建出来"
    return controller, engine, window


def _layer(window):
    helpers.APP.processEvents()
    layer = helpers.find_item(window, "gridLayer")
    assert layer is not None, "地图那一栏的格子层没建出来"
    return (helpers.window_of(window, layer), layer,
            float(layer.property("cell")))


def _mouse(window, row, col, button=Qt.LeftButton):
    """在大图上真发一次按下+抬起（编辑模式的鼠标由路线层统一接）。"""
    target = helpers.find_item(window, "gridLayer")
    assert target is not None and target.isVisible(), "格子层没出来"
    _, layer, cell = _layer(window)
    point = layer.mapToScene(QPointF((col + 0.5) * cell, (row + 0.5) * cell))
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        helpers.APP.sendEvent(helpers.window_of(window, target), QMouseEvent(
            kind, point, point, button, button, Qt.NoModifier))
        helpers.APP.processEvents()


def _picked(window):
    value = window.property("gridPicked")
    return value.toVariant() if hasattr(value, "toVariant") else dict(value or {})


def _cells(controller):
    value = controller.gridCells("长安1")
    return value.toVariant() if hasattr(value, "toVariant") else list(value or [])


def _hover(window):
    value = window.property("gridHover")
    value = value.toVariant() if hasattr(value, "toVariant") else value
    return dict(value or {})


def test_single_click_selects_the_cell_and_changes_nothing():
    """测什么：左键单击已占的格子只是**选中**（琥珀框），数据一个字不动。

    走过的界面：主界面侧栏（选层）→「编辑」→ 大图（单击那一格）。
    """
    controller, engine, window = _edit(cells=[
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}])

    _mouse(window, 0, 0)
    assert _picked(window) == {"row": 0, "col": 0}
    assert _cells(controller) == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]
    ring = helpers.find_item(window, "gridPickedCell")
    assert ring is not None and ring.isVisible()


def test_single_click_on_empty_cell_selects_it_too():
    """测什么：空格子单击也选中它，不会凭空写出坐标。

    走过的界面：「编辑」→ 大图（点空格）。
    """
    controller, engine, window = _edit()
    _mouse(window, 5, 5)
    assert _picked(window) == {"row": 5, "col": 5}
    assert _cells(controller) == []


def test_right_click_opens_the_menu_and_copy_puts_the_coord_on_the_clipboard(
        monkeypatch):
    """测什么：右键出小窗（编号单独一行、带层数），点「复制坐标」写进剪贴板。

    走过的界面：「编辑」→ 大图右键那一格 → 小窗「复制坐标」→ 剪贴板（替身读回）。
    """
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _edit(cells=[
        {"row": 1, "col": 2, "kind": "monster", "name": "血蚊"}])

    _mouse(window, 1, 2, Qt.RightButton)
    menu = helpers.find_item(window, "gridCellMenu")
    assert menu is not None and menu.isVisible()
    coord = helpers.find_item(window, "gridMenuCoord").property("text")
    assert str(coord) == "长安1 2,3" or str(coord).endswith("2,3"), coord
    assert str(helpers.find_item(window, "gridMenuCopy").property("text")) == \
        "复制坐标"

    helpers.click_item(window, helpers.find_item(window, "gridMenuCopy"))
    assert board.text().endswith("2,3"), board.text()


def test_right_click_menu_can_clear_the_cell(monkeypatch):
    """测什么：右键小窗点「清掉」→ 这一格的坐标没了。

    走过的界面：「编辑」→ 大图右键 → 小窗「清掉」。
    """
    helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _edit(cells=[
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}])

    _mouse(window, 0, 0, Qt.RightButton)
    helpers.click_item(window, helpers.find_item(window, "gridMenuClear"))
    helpers.APP.processEvents()
    assert _cells(controller) == []


def test_press_outside_13x13_does_nothing():
    """测什么：图外（第 21 行）移动/按下都不算格子：不悬停出界、不改数据。

    走过的界面：「编辑」→ 大图（在格子区外面移动鼠标、再点一下）。
    """
    controller, engine, window = _edit(cells=[
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}])
    sheet, layer, cell = _layer(window)
    point = layer.mapToScene(QPointF(5.5 * cell, 20.5 * cell))
    before = _hover(window)

    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseMove, point, point,
                                             Qt.NoButton, Qt.NoButton,
                                             Qt.NoModifier))
    helpers.APP.processEvents()
    after = _hover(window)
    assert after in ({}, before)
    if after:
        assert 0 <= int(after.get("row", -1)) < 13
        assert 0 <= int(after.get("col", -1)) < 13

    _mouse(window, 20, 5)
    assert _cells(controller) == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]
