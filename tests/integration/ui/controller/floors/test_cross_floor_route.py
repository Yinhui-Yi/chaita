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


def _field_text(field):
    """坐标格平时那一行字（不含点开后的输入框）。"""
    return str(field.childItems()[0].property("text"))


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


def _open_editor(window, field):
    """点开那一格，返回输入框（不提交）。"""
    assert field is not None, "要点开的那一格没找到"
    helpers.click_item(window, field)
    helpers.APP.processEvents()
    editor = None
    for item in helpers.find_all(window, "coordEditor"):
        if item.isVisible():
            editor = item
    assert editor is not None, "点开之后没出现输入框"
    return editor


def _commit(window, editor, text):
    """把输入框改成 `text` 再回车。"""
    editor.setProperty("text", str(text))
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
    """测什么：「位置」格点开粘 "2,4" → 楼梯位置定成第 2 行第 4 列，格子上只写「2,4」。

    交互顺序：① 点「清单 ›」开这一层 ② 点「＋ 上楼」 ③ 点那一行的位置格
    ④ 粘「2,4」回车 → 断言楼梯位置是 (1,3)、格子上写着「2,4」（不带层数、不带别的字）。
    """
    controller, engine, window = _make()
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True
    helpers.click_item(window, helpers.find_item(window, "floorAddStair"))
    helpers.APP.processEvents()

    row = helpers.find_all(window, "floorStairRow")[0]
    assert helpers.find_item(window, "floorStairPos").property("compact") is True
    assert _field_text(helpers.find_item(window, "floorStairPos")) == "—"
    _paste(window, _inside(row, "floorStairPos"), "2,4")

    stairs = controller.stairsOf("2层")
    assert (stairs[0]["row"], stairs[0]["col"]) == (1, 3)
    assert _field_text(helpers.find_item(window, "floorStairPos")) == "2,4"


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


def test_confirming_the_exit_field_keeps_the_target_floor():
    """测什么：楼梯已经有目标层和落点，点开「出口」**不改字直接回车** → 目标层、落点都不变。

    用户 2026-10-31："楼梯坐标我粘贴后再选中楼层信息就没了" —— 以前点开时被填进了
    **显示文字**，回车后目标层变成一个不存在的层、楼层列表里多一条假层。现在清单上
    不再显示目标层，但点开输入框里仍带着「→3层 6,7」，原样回车必须原样存回去。

    交互顺序：① 开这一层（楼梯通到 3层、落点 6,7）② 点开「出口」直接回车
    → 断言 `to` 还是 "3层"、落点没变、楼层列表里没有多出来的层。
    """
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 11, "dir": "up", "to": "3层",
                 "toRow": 5, "toCol": 6}]})
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True

    row = helpers.find_all(window, "floorStairRow")[0]
    editor = _open_editor(window, _inside(row, "floorStairArrive"))
    assert str(editor.property("text")) == "→3层 6,7"
    _commit(window, editor, str(editor.property("text")))

    stairs = controller.stairsOf("2层")[0]
    assert stairs["to"] == "3层"
    assert (stairs["toRow"], stairs["toCol"]) == (5, 6)
    floors = window.mapFloors()
    floors = floors.toVariant() if hasattr(floors, "toVariant") else floors
    assert sorted(str(f["floor"]) for f in floors) == ["1层", "2层", "3层"]


def test_editing_a_pasted_coord_carries_the_floor():
    """测什么：粘「出口 3层 6,7」之后再点开那一格去改，**输入框里带着层数**；
    改成 "7,8"（不写层数）→ 落点跟着变、目标层不动。

    用户 2026-10-31："你粘贴坐标，再去修改，根本没有层数信息" —— 以前点开只填
    "6,7"，层数看不见，改的时候不知道这是哪一层的坐标。

    交互顺序：① 开这一层 ② 「出口」粘「3层 6,7」回车 ③ 再点开「出口」
    → 断言输入框里有 "3层"；④ 改成 "7,8" 回车 → 落点 (6,7)、目标层还是 3层。
    """
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 11, "dir": "up", "to": "3层"}]})
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True

    row = helpers.find_all(window, "floorStairRow")[0]
    _paste(window, _inside(row, "floorStairArrive"), "3层 6,7")

    row = helpers.find_all(window, "floorStairRow")[0]
    editor = _open_editor(window, _inside(row, "floorStairArrive"))
    assert "3层" in str(editor.property("text")), "点开之后输入框里没有层数"

    _commit(window, editor, "7,8")
    stairs = controller.stairsOf("2层")
    assert (stairs[0]["toRow"], stairs[0]["toCol"]) == (6, 7)
    assert stairs[0]["to"] == "3层", "改坐标不该把目标层改掉"


def test_current_coord_field_also_shows_the_floor_when_editing():
    """「当前」那一格点开也一样带层数（"2层 2,4"）。"""
    controller, engine, window = _make(stairs={
        "2层": [{"row": 1, "col": 11, "dir": "up", "to": ""}]})
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("2层") is not None) is True

    row = helpers.find_all(window, "floorStairRow")[0]
    editor = _open_editor(window, _inside(row, "floorStairPos"))
    assert "2层" in str(editor.property("text"))


def test_crossing_lands_on_the_opposite_stair_when_the_back_is_not_marked():
    """测什么：目标层那座楼梯**没标"通回本层"**，也照样落在它上面。

    用户 2026-10-31："我选路线时如果切层，切换楼层后的起点不对"、"画在错的格子上"。
    以前只认"标了通回本层"的那行，否则落点沿用**上一层同一个坐标** —— 在新层上
    纯属瞎猜。楼梯两头是同一个东西，方向相反那一座就是落脚点。

    交互顺序：① 2层 (1,1) 起笔 → 拖到 (1,12) 的楼梯（通到 3层，3层 那座没标通回）
    ② 松手 → 断言 3层 那段第一格是 3层 的楼梯格 (2,6)，不是 (0,1)。
    """
    controller, engine, window = _make(stairs={
        "2层": [{"row": 0, "col": 11, "dir": "up", "to": "3层"}],
        "3层": [{"row": 2, "col": 6, "dir": "down", "to": ""}]})
    layer = _layer(window)
    _drag_onto(window, layer, (0, 10), [(0, 11)])      # 只能走相邻格

    cells = _routes(controller, "2层")
    assert (cells[-1]["floor"], cells[-1]["row"], cells[-1]["col"]) == \
        ("3层", 2, 6), "没落在目标层那座（方向相反的）楼梯上"


def test_crossing_without_a_target_still_lands_on_the_opposite_stair():
    """上楼梯没选目标层（按方向找相邻层）时，落点同样认"方向相反那一座"。"""
    controller, engine, window = _make(stairs={
        "2层": [{"row": 0, "col": 11, "dir": "up", "to": ""}],
        "3层": [{"row": 2, "col": 6, "dir": "down", "to": ""}]})
    layer = _layer(window)
    _drag_onto(window, layer, (0, 10), [(0, 11)])

    assert window.property("mapFloor") == "3层"
    cells = _routes(controller, "2层")
    assert (cells[-1]["floor"], cells[-1]["row"], cells[-1]["col"]) == \
        ("3层", 2, 6)


def test_the_new_leg_starts_at_the_exit_you_configured(monkeypatch):
    """测什么：切层后新一段的第一格 = **楼梯上配的那个出口**，而且**系统鼠标被移到
    出口那一格的中心**（不是只改数据、也不是拿指针位置顶替出口）。

    用户 2026-11-01："切层后改鼠标坐标"、"鼠标就是鼠标"、"你用了我配的出口了吗"。
    指针这会还停在上一层那一格，所以换层后必须把光标真的挪到落点格上：
    之后的"相邻才接"才有意义。

    交互顺序：① 0层 (1,6) 起笔 ② 拖到 (1,7) 的楼梯（通到 1层，出口配成 13,7）
    ③ 断言新段第一格 = ('1层',12,6)，并且 `_cursor_to` 被调用、坐标就是那一格中心
    ④ 指针挪到出口上面那格 (12,7) → 接上 ('1层',11,6)。
    """
    moved = []

    def fake_cursor_to(x, y):
        moved.append((int(x), int(y)))

    import chaita.ui.controller.monsters.drag as drag_mod
    monkeypatch.setattr(drag_mod, "_cursor_to", fake_cursor_to)

    controller, engine, window = _make(stairs={
        "0层": [{"row": 0, "col": 6, "dir": "up", "to": "1层",
                 "toRow": 12, "toCol": 6}],
        "1层": [{"row": 12, "col": 6, "dir": "down", "to": "0层",
                 "toRow": 0, "toCol": 6}],
    }, floor="0层", floors=("0层", "1层"))
    layer = _layer(window)
    side = float(layer.property("cell"))
    win = helpers.window_of(window, layer)

    def point(row, col):
        return layer.mapToScene(QPointF((col + 0.5) * side,
                                        (row + 0.5) * side))

    def cells():
        value = layer.property("cells")
        value = value.toVariant() if hasattr(value, "toVariant") else value
        return [(c.get("floor"), int(c.get("row", -1)),
                 int(c.get("col", -1))) for c in (value or [])]

    def move(row, col):
        helpers.APP.sendEvent(win, QMouseEvent(
            QEvent.MouseMove, point(row, col), point(row, col), Qt.NoButton,
            Qt.LeftButton, Qt.NoModifier))
        helpers.APP.processEvents()

    helpers.APP.sendEvent(win, QMouseEvent(
        QEvent.MouseButtonPress, point(0, 5), point(0, 5), Qt.LeftButton,
        Qt.LeftButton, Qt.NoModifier))
    helpers.APP.processEvents()
    assert helpers.wait_for(lambda: layer.property("editing") is True,
                            timeout=2.0)
    move(0, 6)                       # 踩到楼梯 → 切到 1层，出口 (12,6)

    assert window.property("mapFloor") == "1层"
    assert cells()[-1] == ("1层", 12, 6), "新段第一格应该是配的那个出口"
    assert layer.property("cellFloor") == "1层"

    # 鼠标被真挪到出口那一格的中心（逻辑坐标 = 窗口位置 + 格中心 × dpr）
    assert moved, "切层后没有移动系统鼠标"
    dpr = float(window.screen().devicePixelRatio())
    want = layer.mapToGlobal(QPointF((6 + 0.5) * side, (12 + 0.5) * side))
    assert abs(moved[-1][0] - round(want.x() * dpr)) <= 2, \
        "鼠标 X 没落在出口那一格（%r vs %r）" % (moved[-1][0], want.x() * dpr)
    assert abs(moved[-1][1] - round(want.y() * dpr)) <= 2, \
        "鼠标 Y 没落在出口那一格（%r vs %r）" % (moved[-1][1], want.y() * dpr)

    move(11, 6)                      # 指针挪到出口上面那一格（相邻）
    assert cells()[-1] == ("1层", 11, 6), "从出口按相邻格接着走"
    assert ("1层", 12, 6) in cells(), "出口那一格要留在路线链里"


def test_stepping_on_a_stair_without_a_target_says_so():
    """测什么：踩到**没选「通到…」**的楼梯 → 不换层，底部给一句提示。

    以前是静默 return：什么都没发生、也没有任何提示，用户只会以为"切层坏了"
    （用户 2026-11-01："切个屁根本不想"）。

    交互顺序：① 1层 (1,6) 起笔 ② 拖到 (1,7) 的上楼楼梯（它没选通到哪层，而
    1层 上面也没有层了）→ 断言 `mapFloor` 还是 1层、底部写着"还没选"。
    """
    controller, engine, window = _make(stairs={
        "1层": [{"row": 0, "col": 6, "dir": "up", "to": ""}],
    }, floor="1层", floors=("0层", "1层"))
    layer = _layer(window)
    side = float(layer.property("cell"))
    win = helpers.window_of(window, layer)

    def point(row, col):
        return layer.mapToScene(QPointF((col + 0.5) * side,
                                        (row + 0.5) * side))

    helpers.APP.sendEvent(win, QMouseEvent(
        QEvent.MouseButtonPress, point(0, 5), point(0, 5), Qt.LeftButton,
        Qt.LeftButton, Qt.NoModifier))
    helpers.APP.processEvents()
    assert helpers.wait_for(lambda: layer.property("editing") is True,
                            timeout=2.0)
    helpers.APP.sendEvent(win, QMouseEvent(
        QEvent.MouseMove, point(0, 6), point(0, 6), Qt.NoButton,
        Qt.LeftButton, Qt.NoModifier))
    helpers.APP.processEvents()

    assert window.property("mapFloor") == "1层", "没选目标层就不该换层"
    assert "还没选" in str(window.property("mapHint")), "得说一句为什么没换层"


def test_the_route_does_not_go_outside_the_map():
    """测什么：拖到地图外面去不算一格（跳层后坐标是偏移算出来的，也会越界）。

    交互顺序：底边从 (12,7) 起笔 ① 往下一格（第 13 行，1基的 14 行）→ 断言那一格没记。
    """
    controller, engine, window = _make(stairs={
        "2层": [{"row": 0, "col": 1, "dir": "up", "to": "3层"}],
        "3层": [{"row": 2, "col": 6, "dir": "down", "to": "2层"}]})
    layer = _layer(window)
    side = float(layer.property("cell"))
    win = helpers.window_of(window, layer)

    def point(row, col):
        return layer.mapToScene(QPointF((col + 0.5) * side,
                                        (row + 0.5) * side))

    helpers.APP.sendEvent(win, QMouseEvent(
        QEvent.MouseButtonPress, point(12, 6), point(12, 6), Qt.LeftButton,
        Qt.LeftButton, Qt.NoModifier))
    helpers.APP.processEvents()
    assert helpers.wait_for(lambda: layer.property("editing") is True,
                            timeout=2.0)
    for row, col in ((12, 7), (13, 7)):
        helpers.APP.sendEvent(win, QMouseEvent(
            QEvent.MouseMove, point(row, col), point(row, col), Qt.NoButton,
            Qt.LeftButton, Qt.NoModifier))
        helpers.APP.processEvents()

    value = layer.property("cells")
    value = value.toVariant() if hasattr(value, "toVariant") else value
    assert [(c["row"], c["col"]) for c in (value or [])] == [
        (12, 6), (12, 7)], "越界的那一格（第 14 行）不该记"


def test_switching_floors_after_a_crossing_keeps_the_layer_in_sync():
    """测什么：跨层画完路线，再点侧栏切层 → 路线层的 `cellFloor` 跟着走。

    以前 `jumpTo()` 给 `cellFloor` 赋值，而它是绑在"现在这一层"上的 —— QML 一赋值
    绑定就永久断了，之后的切层它不跟，新画的一段会标在旧层上（用户 2026-10-31：
    "我选路线时如果切层，切换楼层后的起点不对"）。

    交互顺序：① 在 2层 (1,1) 长按起笔 ② 拖到楼梯格切到 3层 ③ 松手 ④ 点侧栏切到 1层
    → 断言 `cellFloor` 等于 `mapFloor`。
    """
    controller, engine, window = _make(stairs={
        "2层": [{"row": 0, "col": 1, "dir": "up", "to": "3层"}],
        "3层": [{"row": 2, "col": 6, "dir": "down", "to": "2层"}]})
    layer = _layer(window)
    _drag_onto(window, layer, (0, 0), [(0, 1)])
    assert window.property("mapFloor") == "3层"

    rows = helpers.find_all(window, "floorRailRow")
    helpers.click_item(window, rows[len(rows) - 1])
    helpers.APP.processEvents()

    assert window.property("mapFloor") == "1层"
    assert layer.property("cellFloor") == "1层", \
        "路线层的层号没跟着切层（绑定被打断了）"
