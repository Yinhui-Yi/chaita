"""格子编辑的多选（Ctrl+点）——只留真鼠标那条。

规则（用户："编辑模式下能不能加一个ctrl加点击多选？一次性添加多个坐标"）：
Ctrl+点一格 = 勾上，同一格再 Ctrl+点 = 取消；勾着的格子整批记给同一个词条。

**不符合标准、已经删掉的**（都是直调 QML 函数，一次真事件都没发）：
  · `test_ctrl_click_toggles_single_cell` —— `window.gridMultiToggle(0, 0)`
  · `test_ctrl_click_accumulates_then_drops_one` —— 同上
  · `test_assigning_the_selection_records_every_cell` —— 直调 `gridAssignMany`，
    再用 `controller._map_history[0]["mons"][0]["count"]` 断言内部字段
  · `test_assign_many_lands_all_cells_in_one_signal` —— 直调 + 数信号次数
  · `test_leaving_grid_edit_clears_multi_selection` —— `window.gridEditToggle(...)` 直调
  · `test_closing_floor_sheet_clears_multi_selection` —— `window.closeFloorSheet(...)` 直调

**代价（写清楚，别装没事）**：删掉之后，
  · "勾选顺序/去重"、"落格后清空勾选"、"退出编辑/关窗清空勾选"、"整批只发一次信号"
    这四条规则**现在没有自动化测试覆盖**。它们要么补成真事件用例（真 Ctrl+点 + 真拖放，
    拖放那半步在无头环境跑不了），要么挪到单测（需要把规则从 QML 抽到 Python）。
"""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from .... import helpers


def _edit(monsters=None, items=None):
    """起真的 Controller + QML，摆好这一局的起点数据，并打开编辑模式。"""
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": monsters or [{"name": "血蚊", "count": 0}],
        "items": items or [],
        "grid": {"cells": []}}]
    controller.mapHistoryChanged.emit()
    window.setProperty("gridEditOn", True)
    window.setProperty("gridEditFloor", "长安1")
    return controller, engine, window


def _layer(window):
    """主界面地图那一栏的格子覆盖层（顺带等布局）。"""
    window.selectFloor("长安1")
    window.showMap()
    helpers.wait_for(lambda: helpers.find_item(window, "gridLayer") is not None)
    layer = helpers.find_item(window, "gridLayer")
    assert layer is not None, "地图那一栏的格子层没建出来"
    return helpers.window_of(window, layer), layer


def _mouse(window, layer, kind, row, col, modifiers):
    """真鼠标事件打在格子层上（编辑模式的鼠标由路线层统一接）。"""
    target = helpers.find_item(window, "gridLayer")
    assert target is not None and target.isVisible(), "格子层没出来"
    cell = float(layer.property("cell"))
    point = layer.mapToScene(QPointF((col + 0.5) * cell, (row + 0.5) * cell))
    helpers.APP.sendEvent(helpers.window_of(window, target), QMouseEvent(
        kind, point, point, Qt.LeftButton, Qt.LeftButton, modifiers))
    helpers.APP.processEvents()


def _multi(window):
    value = window.property("gridMulti")
    value = value.toVariant() if hasattr(value, "toVariant") else value
    return [(int(c["row"]), int(c["col"])) for c in (value or [])]


def test_ctrl_click_on_the_map_toggles_the_cell():
    """测什么：编辑模式下 Ctrl+单击一格会勾上，再 Ctrl+单击同一格取消。

    交互顺序：① 点侧栏那一行选层 ② 点「编辑」 ③ 按住 Ctrl 在大图 (1,1) 上按下+抬起
    ④ 再来一次同一格 → 断言 `gridMulti` 先多出这一格、再清空。
    """
    controller, engine, window = _edit()
    sheet, layer = _layer(window)

    _mouse(sheet, layer, QEvent.MouseButtonPress, 0, 0, Qt.ControlModifier)
    _mouse(sheet, layer, QEvent.MouseButtonRelease, 0, 0, Qt.ControlModifier)
    assert _multi(window) == [(0, 0)]

    _mouse(sheet, layer, QEvent.MouseButtonPress, 0, 0, Qt.ControlModifier)
    _mouse(sheet, layer, QEvent.MouseButtonRelease, 0, 0, Qt.ControlModifier)
    assert _multi(window) == []
