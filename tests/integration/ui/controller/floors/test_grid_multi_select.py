"""格子编辑的多选（Ctrl+点）集成测试。

规则（用户："编辑模式下能不能加一个ctrl加点击多选？一次性添加多个坐标"）：
· Ctrl+点一格 = 勾上；同一格再 Ctrl+点一次 = 取消；没勾过就是空列表；
· 勾着的时候长按拖，是一整把坐标一起记给同一个词条（数量 = 勾了几格）；
· Ctrl+点**永远不会**变成拖拽（按多久都一样）；
· 退出编辑模式 / 关小窗，勾选清空（不留到下一次）。
"""

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from .... import helpers


def _edit(monsters=None, items=None):
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": monsters or [{"name": "血蚊", "count": 0}],
        "items": items or [],
        "grid": {"cells": []}}]
    window.setProperty("gridEditOn", True)
    window.setProperty("gridEditFloor", "长安1")
    return controller, engine, window


def _layer(window):
    """这一层的格子覆盖层 + 它那 500ms 的长按计时器。"""
    window.setProperty("floorWindows", ["长安1"])
    helpers.APP.processEvents()
    sheet = window.floorSheetOf("长安1")
    layer = sheet.findChildren(QObject, "gridLayer")[0]
    timers = [child for child in layer.findChildren(QObject)
              if child.property("interval") == 500]
    assert len(timers) == 1, "格子覆盖层应该有且只有一个 500ms 长按计时器"
    return sheet, layer, timers[0]


def _mouse(sheet, layer, kind, row, col, modifiers):
    cell = float(layer.property("cell"))
    point = layer.mapToScene(
        QPointF((col + 0.5) * cell, (row + 0.5) * cell))
    helpers.APP.sendEvent(sheet, QMouseEvent(kind, point, point, Qt.LeftButton,
                                             Qt.LeftButton, modifiers))
    helpers.APP.processEvents()


def _raw(window):
    """QML 里的 `var` 属性取出来是 QJSValue，转成 Python 的 list。"""
    value = window.property("gridMulti")
    return value.toVariant() if hasattr(value, "toVariant") else value


def _multi(window):
    return [(int(c["row"]), int(c["col"])) for c in (_raw(window) or [])]


def test_ctrl_click_toggles_single_cell():
    controller, engine, window = _edit()
    window.gridMultiToggle(0, 0)
    assert _multi(window) == [(0, 0)]
    # 同一格再点一次 → 取消
    window.gridMultiToggle(0, 0)
    assert _multi(window) == []


def test_ctrl_click_accumulates_then_drops_one():
    controller, engine, window = _edit()
    window.gridMultiToggle(0, 0)
    window.gridMultiToggle(2, 3)
    window.gridMultiToggle(12, 12)
    assert _multi(window) == [(0, 0), (2, 3), (12, 12)]
    # 取消中间那一格，其余保留原顺序
    window.gridMultiToggle(2, 3)
    assert _multi(window) == [(0, 0), (12, 12)]


def test_dropping_multi_selection_assigns_every_cell():
    controller, engine, window = _edit()
    window.gridMultiToggle(0, 0)
    window.gridMultiToggle(0, 1)
    window.gridMultiToggle(1, 0)
    # 长按拖到「血蚊」词条上：QML 一次把勾中的坐标整批交给 controller
    window.gridAssignMany(_raw(window), "monster", "血蚊", "")
    helpers.APP.processEvents()

    assert controller.gridPositions("长安1", "血蚊") == [
        {"row": 0, "col": 0}, {"row": 0, "col": 1}, {"row": 1, "col": 0}]
    # 数量 = 勾了几格
    assert controller._map_history[0]["mons"][0]["count"] == 3


def test_assign_many_lands_all_cells_in_one_signal():
    """整批只发一次 mapHistoryChanged：多发会让词条行在落格中途被重建。"""
    controller, engine, window = _edit()
    signals = []
    controller.mapHistoryChanged.connect(lambda: signals.append(1))
    window.gridMultiToggle(0, 0)
    window.gridMultiToggle(1, 1)
    window.gridMultiToggle(2, 2)
    window.gridAssignMany(_raw(window), "monster", "血蚊", "")
    helpers.APP.processEvents()

    assert len(signals) == 1
    assert controller.gridPositions("长安1", "血蚊") == [
        {"row": 0, "col": 0}, {"row": 1, "col": 1}, {"row": 2, "col": 2}]
    # 落完就清掉勾选
    assert _multi(window) == []


def test_leaving_grid_edit_clears_multi_selection():
    controller, engine, window = _edit()
    window.gridMultiToggle(0, 0)
    window.gridEditToggle("长安1")       # 再点一次 = 退出编辑
    helpers.APP.processEvents()
    assert window.property("gridEditOn") is False
    assert _multi(window) == []


def test_closing_floor_sheet_clears_multi_selection():
    controller, engine, window = _edit()
    window.setProperty("floorWindows", ["长安1"])
    window.gridMultiToggle(0, 0)
    window.closeFloorSheet("长安1")
    helpers.APP.processEvents()
    assert _multi(window) == []


# ---- Ctrl+点不能被"长按拖拽"吃掉（真鼠标事件）----

def test_ctrl_press_does_not_arm_the_drag_timer():
    """Ctrl+点是勾选，不是拖拽：按得再久也不许起拖拽计时器。

    以前计时器无条件启动，慢点一下就进拖拽会话、这次点击被吞掉，看着就是
    "勾不上第二格"（用户："现在ctrl不能连续选中了"）。
    """
    controller, engine, window = _edit()
    sheet, layer, timer = _layer(window)

    _mouse(sheet, layer, QEvent.MouseButtonPress, 0, 0, Qt.ControlModifier)
    assert timer.property("running") is False
    _mouse(sheet, layer, QEvent.MouseButtonRelease, 0, 0, Qt.ControlModifier)
    assert _multi(window) == [(0, 0)]


def test_plain_press_still_arms_the_drag_timer():
    """不带 Ctrl 按下去照旧开始计时（拖一格是这个手势）。"""
    controller, engine, window = _edit()
    sheet, layer, timer = _layer(window)

    _mouse(sheet, layer, QEvent.MouseButtonPress, 0, 0, Qt.NoModifier)
    assert timer.property("running") is True
    _mouse(sheet, layer, QEvent.MouseButtonRelease, 0, 0, Qt.NoModifier)
    assert timer.property("running") is False
    # 空格子短点 = 取消选中，不会勾上
    assert _multi(window) == []
