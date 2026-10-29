"""格子编辑的单击行为（真鼠标事件打到 GridLayer 上）。

规则（用户："为什么不能删坐标"、"你怎么选出21，6的"）：
· 编辑模式下**单击已占的格子 = 一步删掉**，不用先选中词条；
· 单击空格子 = 取消选中；
· 13×13 之外不算格子：`cellAt` 返回空，按下不悬停、不抓、不删。

注意：这一层的小窗会被主窗口重建，`floorSheetOf` 每次现取，别把旧对象存下来。
"""

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from .... import helpers


def _edit(cells=None):
    """起一套窗口。**engine 必须活着**：它是窗口的爹，被回收了窗口就没了。"""
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": [{"name": "血蚊", "count": 0},
                 {"name": "绿水母", "count": 0}],
        "items": [],
        "grid": {"cells": cells or []}}]
    window.setProperty("gridEditOn", True)
    window.setProperty("gridEditFloor", "长安1")
    window.setProperty("floorWindows", ["长安1"])
    helpers.wait_for(lambda: window.floorSheetOf("长安1") is not None)
    return controller, engine, window


def _layer(window):
    """现取这一层的小窗和格子层。"""
    helpers.APP.processEvents()
    sheet = window.floorSheetOf("长安1")
    assert sheet is not None, "这一层的小窗没建出来"
    layer = sheet.findChildren(QObject, "gridLayer")[0]
    return sheet, layer, float(layer.property("cell"))


def _click(window, row, col):
    sheet, layer, cell = _layer(window)
    point = layer.mapToScene(
        QPointF((col + 0.5) * cell, (row + 0.5) * cell))
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        helpers.APP.sendEvent(sheet, QMouseEvent(kind, point, point,
                                                 Qt.LeftButton, Qt.LeftButton,
                                                 Qt.NoModifier))
        helpers.APP.processEvents()


def _cells(controller):
    return controller._map_history[0]["grid"]["cells"]


def test_click_occupied_cell_deletes_it_in_one_go():
    controller, engine, window = _edit(cells=[
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 1, "col": 1, "kind": "monster", "name": "绿水母"}])
    window.setProperty("gridSelected", "")

    _click(window, 0, 0)

    assert _cells(controller) == [
        {"row": 1, "col": 1, "kind": "monster", "name": "绿水母"}]
    assert controller._map_history[0]["mons"][0]["count"] == 0


def test_click_empty_cell_only_cancels_selection():
    controller, engine, window = _edit(cells=[
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}])
    window.setProperty("gridSelected", "血蚊")

    _click(window, 5, 5)

    assert str(window.property("gridSelected") or "") == ""
    # 一个格子都没动
    assert _cells(controller) == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]


def test_cell_at_outside_13x13_is_empty():
    controller, engine, window = _edit()
    sheet, layer, cell = _layer(window)

    def inside(row, col):
        value = layer.cellAt((col + 0.5) * cell, (row + 0.5) * cell)
        value = value.toVariant() if hasattr(value, "toVariant") else value
        return bool(value)

    assert inside(0, 0) is True
    assert inside(12, 12) is True
    assert inside(13, 0) is False        # 第 14 行
    assert inside(20, 5) is False        # 用户看到的 "21,6"
    assert inside(0, 13) is False


def _hover(window):
    value = window.property("gridHover")
    value = value.toVariant() if hasattr(value, "toVariant") else value
    return dict(value or {})


def test_press_outside_13x13_does_nothing():
    """出界按下：不悬停、不动数据（以前能拖出第 21 行）。"""
    controller, engine, window = _edit(cells=[
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}])
    sheet, layer, cell = _layer(window)
    point = layer.mapToScene(QPointF(5.5 * cell, 20.5 * cell))
    # 别断言"悬停一定是空"：窗口一冒出来，Qt 就可能按**真实光标位置**先发一次 enter，
    # 那是环境状态。只断言"出界这一下没改动它"。
    before = _hover(window)

    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseMove, point, point,
                                             Qt.NoButton, Qt.NoButton,
                                             Qt.NoModifier))
    helpers.APP.processEvents()
    after = _hover(window)
    # 出界的点绝不能被当成格子：要么悬停没变，要么被清掉；
    # 不许出现"第 21 行"这种格子（那正是以前的 bug）。
    assert after in ({}, before)
    if after:
        assert 0 <= int(after.get("row", -1)) < 13
        assert 0 <= int(after.get("col", -1)) < 13

    _click(window, 20, 5)
    assert _cells(controller) == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]

