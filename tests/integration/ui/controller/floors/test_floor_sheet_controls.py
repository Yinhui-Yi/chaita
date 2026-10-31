"""「这一层」小窗上剩下的控件（**集成测试**，真点击/真打字）。

覆盖：地图那一栏的「编辑」开关、怪名只读、点「路线 1」开链窗口、✕ 关窗、「＋」开下一层、
编辑模式下行的"位置 1,1"跟着格子变、路线那半截实时数值、右下角拉大小。

真值手写：编辑按钮点一下进编辑（文字变「完成」）、再点退出；怪名点不动；点「路线 1」把
那条路线打开；✕ 关掉这扇窗；「＋」开下一层。

标准见 `tests/integration/README.md`。驱动：点「清单 ›」开窗 → 点窗/地图条上的控件，
或在图上右键/把格子拖到行上（真 drop 事件）。断言读公开属性（`window.floorWindows /
routeWindow / routeFloor / floorSizes`、界面文字）。
"""

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from .... import helpers


def _sheet(floors=None, mons=None, routes=None):
    """摆好层记录，再点「清单 ›」把这层的小窗打开。"""
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
    helpers.APP.processEvents()

    assert helpers.wait_for(
        lambda: helpers.find_item(window, "mapSheet") is not None), \
        "地图那一栏没出来"
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf(entries[0]["floor"]) is not None), \
        "清单没打开"
    helpers.APP.processEvents()
    return controller, engine, window


def _type(window, item, text):
    """在输入框里打完字再按回车（走 editingFinished）。"""
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


def test_grid_edit_button_lives_in_the_map_strip():
    """测什么：编辑开关在地图那条动作里，点一下退出（文字变「编辑」），再点又进编辑。

    交互顺序：① 点「清单 ›」开这一层 —— **开清单会自动进编辑模式**，所以按钮此时写
    「完成」 ② 点「完成」→ 断言 `gridEditOn` 为假、文字变「编辑」 ③ 再点一次 → 断言
    又进编辑；小窗里没有那个旧按钮（它以前在地图截图右上角）。
    """
    controller, engine, window = _sheet()
    helpers.APP.processEvents()

    button = helpers.find_item(window, "mapGridEdit")
    assert button is not None
    # 开清单 = 自动进编辑（用户："我怎么标？"）
    assert window.property("gridEditOn") is True
    assert button.property("text") == "完成"

    helpers.click_item(window, button)
    assert window.property("gridEditOn") is False
    assert helpers.find_item(window, "mapGridEdit").property("text") == "编辑"

    helpers.click_item(window, helpers.find_item(window, "mapGridEdit"))
    assert window.property("gridEditOn") is True
    assert helpers.find_item(window, "floorGridEdit") is None


def test_monster_name_is_read_only():
    """测什么：清单里的怪名是只读文本，点它/往里打字都改不动数据。

    交互顺序：① 点「清单 ›」开这一层（有一只血蚊）② 点那一行的名字 ③ 直接改那个控件的
    text 再回车 → 断言控件是 Text（没有 placeholderText）、数据里还是「血蚊」。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    field = helpers.find_item(window, "floorMonName")
    assert field is not None
    # 它是 Text 不是 TextField：没有 placeholderText / 没有可编辑的输入框
    assert field.property("placeholderText") is None
    assert field.property("text") == "血蚊"
    _type(window, field, "血蚊王")
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["name"] == "血蚊"


def test_route_open_click_opens_that_route():
    """测什么：点路线那一行 → 打开对应的链窗口，带上层名和序号。

    交互顺序：① 点「清单 ›」开这一层（有一条路线）② 点那一行的「路线 1」
    → 断言 `routeWindow` 存在、`routeFloor/routeIndex` 对得上。
    """
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
    """测什么：点小窗右上角的 ✕ → 这扇窗关掉。

    交互顺序：① 点「清单 ›」开这一层 ② 点 ✕ → 断言 `floorWindows` 空了。
    """
    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorClose"))
    helpers.APP.processEvents()

    assert _windows(window) == []


def test_more_button_opens_the_next_floor():
    """测什么：点小窗的「＋」→ 接着开下一层的小窗。

    交互顺序：① 点「清单 ›」开长安1 ② 点「＋」→ 断言长安2 的窗也开着。
    """
    controller, engine, window = _sheet(floors=["长安1", "长安2"])
    helpers.click_item(window, helpers.find_item(window, "floorMore"))
    helpers.APP.processEvents()

    assert "长安2" in _windows(window)


# ---- 编辑模式的位置文字、路线那半截计算值 ----

def test_position_text_follows_grid_cells():
    """测什么：编辑模式下把一格拖到怪那一行 → 那一行的位置文字变成"位置 1,1"。

    交互顺序：① 点「清单 ›」开这一层（**自动进编辑模式**）② 把 (1,1) 这一格拖到
    怪那一行上松手 → 断言 `floorMonPos` 先写"没标位置"、之后写"位置 1,1"。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    assert "没标位置" in str(
        helpers.find_item(window, "floorMonPos").property("text"))

    assert window.property("gridEditOn") is True, "开清单应该自动进编辑模式"

    row = helpers.find_all(window, "floorMonRow")[0]
    helpers.drop_cells(window, row, {"row": 0, "col": 0})
    helpers.APP.processEvents()

    # 显示是 1 开始的（内部 0 开始）
    assert "位置 1,1" in str(helpers.find_item(window, "floorMonPos").property(
        "text"))


def test_route_computed_text_shows_live_stats():
    """测什么：路线那一行右边写的是**实时算出来的**数值（不是存下来的文字）。

    交互顺序：① 点「清单 ›」开这一层（有一条路线）→ 断言 `routeComputed` 的文字等于
    `routeStatsFor` 算的、并且以「血 」开头。
    """
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
    """测什么：拖右下角的把手 → 窗变大，而且新尺寸记到这一层上（下次开还这么大）。

    交互顺序：① 点「清单 ›」开这一层 ② 按住右下角把手往右下拖 (60, 40) 松手
    → 断言宽高都变大、`floorSizes["长安1"]` 记下新宽度。
    """
    controller, engine, window = _sheet()
    sheet = window.floorSheetOf("长安1")
    grip = sheet.findChildren(QObject, "floorGrip")[0]     # 右下角
    before = (sheet.width(), sheet.height())

    _drag(sheet, grip, 60, 40)

    after = (sheet.width(), sheet.height())
    assert after[0] > before[0], "往右下拖宽度应该变大"
    assert after[1] > before[1], "往右下拖高度应该变大"
    sizes = window.property("floorSizes")
    sizes = sizes.toVariant() if hasattr(sizes, "toVariant") else sizes
    assert int(sizes["长安1"]["w"]) == after[0]
