"""「这一层」小窗上剩下的控件（真点击/真打字）：编辑开关、改怪名、点路线、关窗、切下一层。

真值手写：编辑按钮点一下进编辑（文字变「完成」）、再点是退出；改怪名写回那一行；
点「路线 1」把那条路线打开；✕ 关掉这扇窗；「＋」开下一层。
"""

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from .... import helpers


def _sheet(floors=None, mons=None, routes=None):
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"}]
    # 怪物行读的是缓存属性，不发信号界面还拿着上一轮的名单
    controller.monstersChanged.emit()
    entries = []
    for floor in floors or ["长安1"]:
        entries.append({
            "floor": floor, "url": "",
            "mons": list(mons or []), "items": [],
            "grid": {"cells": []}, "routes": list(routes or [])})
    controller._map_history = entries
    controller.mapHistoryChanged.emit()
    window.setProperty("floorWindows", [entries[0]["floor"]])
    helpers.wait_for(lambda: window.floorSheetOf(entries[0]["floor"]) is not None)
    return controller, engine, window


def _type(window, item, text):
    item.forceActiveFocus()
    helpers.APP.processEvents()
    item.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(item.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def _windows(window):
    value = window.property("floorWindows")
    return value.toVariant() if hasattr(value, "toVariant") else value


def test_grid_edit_button_toggles_edit_mode():
    controller, engine, window = _sheet()
    button = helpers.find_item(window, "floorGridEdit")
    assert button.property("label") == "编辑"

    helpers.click_item(window, button)
    assert window.property("gridEditOn") is True
    assert helpers.find_item(window, "floorGridEdit").property("label") == "完成"

    helpers.click_item(window, helpers.find_item(window, "floorGridEdit"))
    assert window.property("gridEditOn") is False


def test_monster_name_field_renames_row():
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    _type(window, helpers.find_item(window, "floorMonName"), "血蚊王")

    assert controller._map_history[0]["mons"][0]["name"] == "血蚊王"


def test_route_open_click_opens_that_route():
    controller, engine, window = _sheet(
        routes=[{"at": "10:00", "cells": [{"row": 0, "col": 0}]}])
    helpers.click_item(window, helpers.find_item(window, "routeOpen"))
    helpers.APP.processEvents()

    value = window.property("routeWindow")
    value = value.toQObject() if hasattr(value, "toQObject") else value
    assert value is not None
    assert window.property("routeFloor") == "长安1"
    assert window.property("routeIndex") == 0


def test_close_button_closes_the_sheet():
    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorClose"))
    helpers.APP.processEvents()

    assert _windows(window) == []


def test_more_button_opens_the_next_floor():
    controller, engine, window = _sheet(floors=["长安1", "长安2"])
    helpers.click_item(window, helpers.find_item(window, "floorMore"))
    helpers.APP.processEvents()

    assert "长安2" in _windows(window)


# ---- 没图时的占位、编辑模式的位置文字、路线那半截计算值 ----

def test_position_text_follows_grid_cells():
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    window.gridEditToggle("长安1")
    helpers.APP.processEvents()

    assert "没标位置" in helpers.find_item(window, "floorMonPos").property("text")

    controller.assignGridCell("长安1", 0, 0, "monster", "血蚊")
    helpers.APP.processEvents()

    # 显示是 1 开始的（内部 0 开始）
    assert "位置 1,1" in helpers.find_item(window, "floorMonPos").property("text")


def test_route_computed_text_shows_live_stats():
    controller, engine, window = _sheet(
        routes=[{"at": "10:00", "cells": [{"row": 0, "col": 0}]}])

    text = helpers.find_item(window, "routeComputed").property("text")

    assert text == window.routeStatsFor("长安1", 0)
    assert text.startswith("血 ")


# ---- 右下角那个拉大小的把手 ----

def _drag(sheet, item, dx, dy):
    """在这个控件上按下 → 往 (dx, dy) 拖 → 松手（真鼠标事件）。"""
    start = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    end = QPointF(start.x() + dx, start.y() + dy)
    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseButtonPress, start,
                                             start, Qt.LeftButton,
                                             Qt.LeftButton, Qt.NoModifier))
    helpers.APP.processEvents()
    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseMove, end, start,
                                             Qt.NoButton, Qt.LeftButton,
                                             Qt.NoModifier))
    helpers.APP.processEvents()
    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseButtonRelease, end,
                                             end, Qt.LeftButton, Qt.NoButton,
                                             Qt.NoModifier))
    helpers.APP.processEvents()


def test_resize_grip_grows_the_sheet():
    controller, engine, window = _sheet()
    sheet = window.floorSheetOf("长安1")
    grip = sheet.findChildren(QObject, "floorGrip")[0]     # 右下角
    before = (sheet.width(), sheet.height())

    _drag(sheet, grip, 60, 40)

    after = (sheet.width(), sheet.height())
    assert after[0] > before[0], "往右下拖宽度应该变大"
    assert after[1] > before[1], "往右下拖高度应该变大"
    # 大小记到这一层上（下次开还这么大）
    sizes = window.property("floorSizes")
    sizes = sizes.toVariant() if hasattr(sizes, "toVariant") else sizes
    assert int(sizes["长安1"]["w"]) == after[0]
