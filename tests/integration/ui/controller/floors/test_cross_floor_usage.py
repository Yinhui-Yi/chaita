"""跨层的**真实使用路径**：只点界面上的东西，证明用户能做到。

为什么单开一个文件：跨层原有的用例大多直接调 `window.routeEnterCell(...)`，
证明的是"函数被调用后会切"，证明不了"用户在界面上标完楼梯、长按拖着走过去会切"。
用户 2026-10-30 连着三句："我标了！！！！"、"路线移到楼梯要换层！！！！"、
"切层还是失败" —— 真机不切，正是因为标楼梯那几步（加行 → 粘坐标 → 选目标层）
在测试里从来没被点过一遍。

这里的每一步都是真实控件 + 真实鼠标：
  · 按钮用 `helpers.click_item`（合成按下/抬起，走 QML 的 onClicked）
  · 坐标用"点开坐标格 → 粘文本 → 回车"（走 CoordField.onEditingFinished）
  · 路线用"按下 → 长按 350ms 起笔 → 一格一格移 → 松手"（走 RouteLayer）
不用 Slot 直调。

两个容易写错的点（写在这里免得下一个人再踩）：
  · 格子边长 `cell` 要**等布局**：刚 showMap 时还是 0，算出来的点会落到窗口角落，
    事件打空、断言全红；所以先 wait `cell > 0` 再算坐标。
  · 对角不算一格（RouteLayer 只认相邻），从 (0,4) 直接去 (1,3) 会被丢掉，
    必须走正交的一步。
  · 松手后 `routeLayer.cells` 会被清空（路线已经存进 controller 了），别拿它当断言。
"""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from .... import helpers


def _make(floors=("1层", "2层", "3层"), floor="2层", stairs=None):
    controller, engine, window = helpers.make_controller()
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
    """路线层；**先等格子边长算出来**，否则后面算的坐标全落在 (0,0)。"""
    layer = helpers.find_item(window, "routeLayer")
    assert layer is not None
    assert helpers.wait_for(
        lambda: float(layer.property("cell") or 0) > 0, timeout=5.0), \
        "格子边长一直是 0，地图没摆好"
    return layer


def _point(layer, row, col):
    side = float(layer.property("cell"))
    return layer.mapToScene(QPointF((col + 0.5) * side, (row + 0.5) * side))


def _long_press_then_drag(window, layer, start, steps):
    """真鼠标：按下 → 等长按起笔 → 一格一格移（只走正交相邻）。"""
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


def _click_cell(window, layer, row, col):
    """在某一格上真点一下（按下→抬起，不按住），走 RouteLayer 的 tapped。"""
    point = _point(layer, row, col)
    target = helpers.window_of(window, layer)
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        helpers.APP.sendEvent(target, QMouseEvent(
            kind, point, point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        helpers.APP.processEvents()


def _paste_coord(window, name, text):
    """点开坐标格 → 粘 "2,4" → 回车（用户："可以通过粘贴修改坐标"）。
    现在坐标格上带着层数（"2层 2,4"），粘进去的只要最后两个数字对就行。"""
    field = helpers.find_item(window, name)
    assert field is not None, "没找到坐标格 %s" % name
    helpers.click_item(window, field)
    helpers.APP.processEvents()
    editor = None
    for item in helpers.find_all(window, "coordEditor"):
        if item.isVisible():
            editor = item
    assert editor is not None, "坐标格没变成输入框"
    editor.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(editor.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def _type_field(window, field_name, editor_name, text):
    """点开一格（坐标格/层号格）→ 打字 → 回车。"""
    field = helpers.find_item(window, field_name)
    assert field is not None, "没找到 %s" % field_name
    helpers.click_item(window, field)
    helpers.APP.processEvents()
    editor = None
    for item in helpers.find_all(window, editor_name):
        if item.isVisible():
            editor = item
    assert editor is not None, "%s 点开之后没出现输入框" % field_name
    editor.setProperty("text", str(text))
    helpers.APP.processEvents()
    helpers.APP.sendEvent(editor.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def _type_target(window, controller, floor, typed):
    """真点「通到…」那一格，**打字**回车（用户 2026-10-31 骂掉了"点一下换一层"的循环）。"""
    _type_field(window, "floorStairTarget", "floorEditor", typed)
    rows = controller.stairsOf(floor)
    return str(rows[0].get("to") or "") if rows else ""


def _floor_names(window):
    value = window.mapFloors()
    value = value.toVariant() if hasattr(value, "toVariant") else value
    return [str((row or {}).get("floor") or "") for row in (value or [])]


def test_marking_a_stair_in_the_sheet_then_walking_on_it_switches_the_floor():
    """测什么：清单里标完楼梯（加行/粘坐标/打层号）→ 关清单 → 图上长按拖过去 → 换层。

    交互顺序：① 点「清单 ›」开这一层 ② 点「＋ 上楼梯」 ③ 在「当前」格粘「2,4」
    ④ 在「通到…」打「3」回车 ⑤ 点 ✕ 关清单 ⑥ 在大图上长按第 1 行第 4 列起笔、
    往下拖一格（踩到楼梯）松手 → 断言 `mapFloor` 变成 3层。"""
    controller, engine, window = _make()
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True, "清单没打开"

    helpers.click_item(window, helpers.find_item(window, "floorAddStair"))
    helpers.APP.processEvents()
    assert len(helpers.find_all(window, "floorStairRow")) == 1
    _paste_coord(window, "floorStairPos", "2,4")
    assert (controller.stairsOf("2层")[0]["row"],
            controller.stairsOf("2层")[0]["col"]) == (1, 3), "粘的坐标没写进楼梯"
    # 打层号 "3" → 认成读过的 "3层"
    assert _type_target(window, controller, "2层", "3") == "3层", \
        "「通到…」里打 3 没认成 3层"

    helpers.click_item(window, helpers.find_item(window, "floorClose"))
    helpers.APP.processEvents()
    assert window.floorSheetOf("2层") is None, "清单没关掉，会挡住地图"

    layer = _layer(window)
    _long_press_then_drag(window, layer, (0, 3), [(1, 3)])
    assert window.property("mapFloor") == "3层", "踩到标好的楼梯没换层"


def test_long_pressing_a_marked_stair_switches_without_opening_the_sheet():
    """测什么：不开清单、非编辑模式下，长按拖到楼梯格就换层，且不需要提示。

    交互顺序：① 不开清单、非编辑模式下 ② 在大图 (1,1) 按住 350ms 起笔
    ③ 往下一格拖（楼梯）④ 松手 → 断言换到 3层、且 `mapHint` 为空。"""
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 3, "dir": "up", "to": "3层",
                 "toRow": -1, "toCol": -1}],
        "3层": [{"row": 6, "col": 6, "dir": "down", "to": "2层",
                 "toRow": -1, "toCol": -1}]})
    assert window.property("gridEditOn") is False, "这条用例要在非编辑模式下跑"

    layer = _layer(window)
    _long_press_then_drag(window, layer, (0, 3), [(1, 3)])

    assert window.property("mapFloor") == "3层"
    # 3层 有"通回 2层"的楼梯 → 落在它上面，不用提示
    assert window.property("mapHint") == ""


def test_stepping_on_a_stair_creates_the_next_floor_when_it_was_never_read():
    """测什么：只读到通天塔2、楼梯也没选目标层 → 踩上去自己建出通天塔3 并切过去。

    交互顺序：① 只读到通天塔2（没有别的层）② 长按起笔拖到那个没选目标层的楼梯上
    ③ 松手 → 断言 `mapFloor` 是通天塔3、层列表里也有它。"""
    controller, engine, window = _make(floors=("通天塔2",), floor="通天塔2",
                                       stairs={"通天塔2": [
                                           {"row": 1, "col": 3, "dir": "up",
                                            "to": ""}]})
    layer = _layer(window)
    _long_press_then_drag(window, layer, (0, 3), [(1, 3)])

    assert window.property("mapFloor") == "通天塔3"
    assert "通天塔3" in _floor_names(window), "切过去的那一层没进层列表"


def test_clicking_a_stair_on_the_map_switches_to_its_floor():
    """测什么：在楼梯格上**点一下**（不拖）就换到它通的那一层。

    交互顺序：① 在大图上点一下楼梯那一格（按下+抬起，不按住）
    ② 断言 `mapFloor` 变成 3层。"""
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 3, "dir": "up", "to": "3层",
                 "toRow": -1, "toCol": -1}]})
    assert window.property("gridEditOn") is False

    layer = _layer(window)
    _click_cell(window, layer, 1, 3)
    assert window.property("mapFloor") == "3层", "点了楼梯没换层"


def test_clicking_a_plain_cell_does_not_switch():
    """测什么：点非楼梯格什么都不发生（不能变成"随便点都跳层"）。

    交互顺序：① 在大图上点一下普通格子（第 6 行第 6 列）→ 断言楼层没变。"""
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 3, "dir": "up", "to": "3层",
                 "toRow": -1, "toCol": -1}]})

    layer = _layer(window)
    _click_cell(window, layer, 5, 5)
    assert window.property("mapFloor") == "2层"


def test_clicking_a_stair_creates_the_next_floor_when_none_is_known():
    """测什么：点楼梯时那一层还没读过 → 按层号建出来再切过去。

    交互顺序：① 只读到通天塔2 ② 点一下那个楼梯 → 断言建出通天塔3 并切过去。"""
    controller, engine, window = _make(floors=("通天塔2",), floor="通天塔2",
                                       stairs={"通天塔2": [
                                           {"row": 1, "col": 3, "dir": "up",
                                            "to": ""}]})
    layer = _layer(window)
    _click_cell(window, layer, 1, 3)
    assert window.property("mapFloor") == "通天塔3"
    assert "通天塔3" in _floor_names(window)


def test_a_stair_can_go_to_a_floor_that_was_never_read():
    """测什么：0层→2层，目标层没读过也能在「通到…」里打进去，打完点楼梯真的切过去。

    交互顺序：① 点「清单 ›」 ② 在「通到…」打「2」回车（那层还没读过）
    ③ 关清单 ④ 点一下楼梯 → 断言切成 2层、层列表里有它。"""
    controller, engine, window = _make(floors=("0层",), floor="0层",
                                       stairs={"0层": [
                                           {"row": 1, "col": 3, "dir": "up",
                                            "to": ""}]})
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("0层") is not None) is True
    assert _type_target(window, controller, "0层", "2") == "2层", \
        "打 2 没拼出 2层"

    helpers.click_item(window, helpers.find_item(window, "floorClose"))
    helpers.APP.processEvents()
    layer = _layer(window)
    _click_cell(window, layer, 1, 3)
    assert window.property("mapFloor") == "2层"
    assert "2层" in _floor_names(window), "跳过去的 2层 没进层列表"


def test_coordinates_carry_the_floor_number():
    """测什么：楼梯行两个坐标格分别写着本层和「→目标层」的层数。

    交互顺序：① 点「清单 ›」开这一层 ② 读那一行两个坐标格的文字
    → 断言左格是「2层 2,4」、右格是「→3层 6,7」。"""
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 3, "dir": "up", "to": "3层",
                 "toRow": 5, "toCol": 6}]})
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True
    helpers.APP.processEvents()

    here = helpers.texts_of(helpers.find_item(window, "floorStairPos"))
    there = helpers.texts_of(helpers.find_item(window, "floorStairArrive"))
    assert "2层 2,4" in here, here
    assert "→3层 6,7" in there, there


def test_clicking_the_peeking_corner_switches_to_that_floor():
    """测什么：点大图后面露出的那条带子 = 切到下面那一层（点卡片中心不算）。

    交互顺序：① 在大图右下角露出来的那条 14px 带子上点一下
    ② 断言 `mapFloor` 变成下面那一层。"""
    controller, engine, window = _make(floor="3层")
    peeks = helpers.find_all(window, "mapPeek")
    assert peeks, "3层 下面还压着 2层，应该露出一个角"
    peek = peeks[0]
    assert peek.width() > 20, "露出那一角还没摆好尺寸"
    point = peek.mapToScene(QPointF(peek.width() - 5, peek.height() - 5))
    target = helpers.window_of(window, peek)
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        helpers.APP.sendEvent(target, QMouseEvent(
            kind, point, point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        helpers.APP.processEvents()
    assert window.property("mapFloor") == "2层", "点露出来的那一角没切层"
