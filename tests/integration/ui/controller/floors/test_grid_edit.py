"""格子编辑：把坐标拖到词条上 → 落进那一层的 grid，数量跟着位置走（**集成测试**）。

链是 QML 的 DropArea（真 enter/move/drop 事件）→ `gridAssignMany` → `controller.assignGridCell`
→ `_resync_count` → 层记录。期望值从规则手写：一格只留一样；同名怪的数量 = 它在 grid 里
的格数；**同名资源按"名字+效果"认**（两个血瓶 150 / 300 各标各的，不互相串）。

标准见 `tests/integration/README.md`。驱动：点「清单 ›」开这一层（自动进编辑模式）→
把格子真拖到某一行上松手 / 右键点「清掉」/ 点 ✕ 关窗。断言读公开 Slot
（`controller.gridCells / gridPositions`）和 `window.gridEditOn`。

**改掉的**：原来 4 条都直调 `window.gridAssign(...)` / `setProperty("gridEditOn")` /
`closeFloorSheet(...)`，一次鼠标事件都没有；现在全走真 drop / 右键菜单 / 关闭按钮。
"""

from .... import helpers


def _open_sheet(items=None, mons=None):
    """摆好这一层，点「清单 ›」开窗（开清单会自动进编辑模式）。"""
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": mons or [{"name": "血蚊", "count": 1}],
        "items": items or [],
        "grid": {"cells": []},
        "routes": []}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    assert helpers.wait_for(
        lambda: helpers.find_item(window, "mapSheet") is not None), \
        "地图那一栏没出来"
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("长安1") is not None), "清单没打开"
    helpers.APP.processEvents()
    assert window.property("gridEditOn") is True, "开清单应该自动进编辑模式"
    return controller, engine, window


def _cells(controller):
    value = controller.gridCells("长安1")
    return value.toVariant() if hasattr(value, "toVariant") else list(value or [])


def test_dropping_two_cells_on_a_monster_row_resyncs_its_count():
    """测什么：把两格都拖到同一只怪那一行 → 两格进 grid，这只怪的数量变成 2。

    交互顺序：① 点「清单 ›」开这一层（自动进编辑）② 把 (1,1) 拖到血蚊那一行松手
    ③ 再把 (1,2) 拖到同一行 → 断言 grid 里两格、`mons[0].count == 2`。
    """
    controller, engine, window = _open_sheet()
    row = helpers.find_all(window, "floorMonRow")[0]

    helpers.drop_cells(window, row, {"row": 0, "col": 0})
    helpers.APP.processEvents()
    helpers.drop_cells(window, row, {"row": 0, "col": 1})
    helpers.APP.processEvents()

    assert _cells(controller) == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 0, "col": 1, "kind": "monster", "name": "血蚊"}]
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 2, "数量应该等于它占的格数"


def test_clearing_the_cell_by_right_click_zeroes_the_count():
    """测什么：右键把那一格「清掉」→ grid 空、这只怪的数量归零。

    交互顺序：① 开「清单 ›」② 把 (1,1) 拖到血蚊那一行 ③ 在大图上右键这一格
    ④ 点小窗「清掉」→ 断言 grid 空、`mons[0].count == 0`。
    """
    controller, engine, window = _open_sheet()
    row = helpers.find_all(window, "floorMonRow")[0]
    helpers.drop_cells(window, row, {"row": 0, "col": 0})
    helpers.APP.processEvents()
    assert len(_cells(controller)) == 1

    # 在大图上右键 (1,1)，再点小窗里的「清掉」
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    layer = helpers.find_item(window, "routeLayer")
    helpers.wait_for(lambda: float(layer.property("cell") or 0) > 0)
    side = float(layer.property("cell"))
    point = layer.mapToScene(QPointF(0.5 * side, 0.5 * side))
    target = helpers.window_of(window, layer)
    for kind, button in ((QEvent.MouseButtonPress, Qt.RightButton),
                         (QEvent.MouseButtonRelease, Qt.NoButton)):
        helpers.APP.sendEvent(target, QMouseEvent(
            kind, point, point, Qt.RightButton, button, Qt.NoModifier))
        helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "gridMenuClear"))
    helpers.APP.processEvents()

    assert _cells(controller) == []
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 0, "一格都不标了，数量应该归零"


def test_two_same_name_items_keep_separate_positions():
    """测什么：两个同名血瓶（效果不同）各拖各的格 → 坐标不互相串，数量各算各的。

    交互顺序：① 开「清单 ›」② 把 (1,1) 拖到第一个血瓶那一行 ③ 把 (1,2) 拖到第二个
    血瓶那一行 → 断言 `gridPositions(名字, 效果)` 各是各的、两个数量都是 1。
    """
    controller, engine, window = _open_sheet(items=[
        {"name": "血瓶", "effect": "体力 +150", "count": 1,
         "icon": "potion_red"},
        # 第二个血瓶的效果是用户自己改过的（`effect_manual`）；不标这个，
        # 界面会按道具表把效果统一成 +150 —— 那两只就分不出来了
        {"name": "血瓶", "effect": "体力 +300", "count": 1,
         "icon": "potion_red", "effect_manual": True}])
    rows = helpers.find_all(window, "floorItemRow")
    assert len(rows) == 2

    helpers.drop_cells(window, rows[0], {"row": 0, "col": 0})
    helpers.APP.processEvents()
    # 落一次格会重建这些行 → 重新拿一遍，别抓着已销毁的委托
    rows = helpers.find_all(window, "floorItemRow")
    helpers.drop_cells(window, rows[1], {"row": 0, "col": 1})
    helpers.APP.processEvents()

    assert controller.gridPositions("长安1", "血瓶", "体力 +150") == [
        {"row": 0, "col": 0}]
    assert controller.gridPositions("长安1", "血瓶", "体力 +300") == [
        {"row": 0, "col": 1}]
    items = window.sheetItems("长安1")
    items = items.toVariant() if hasattr(items, "toVariant") else list(items or [])
    by_effect = {i["effect"]: i["count"] for i in items}
    assert by_effect["体力 +150"] == 1
    assert by_effect["体力 +300"] == 1


def test_closing_the_sheet_leaves_grid_edit():
    """测什么：点小窗的 ✕ → 退出编辑模式（编辑层和坐标线跟着收起来）。

    交互顺序：① 点「清单 ›」开这一层（自动进编辑）② 点 ✕ → 断言 `gridEditOn` 为假、
    `gridEditFloor` 清空。
    """
    controller, engine, window = _open_sheet()
    helpers.click_item(window, helpers.find_item(window, "floorClose"))
    helpers.APP.processEvents()

    assert window.property("gridEditOn") is False
    assert window.property("gridEditFloor") == ""


# ---- 编辑模式长按抓一格，拖到「这一层」某一行上松手 ----

def _press_and_hold(window):
    """在大图 (1,1) 上按住不动，等它起笔（编辑模式 → 抓起这一格）。"""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    layer = helpers.find_item(window, "routeLayer")
    helpers.wait_for(lambda: float(layer.property("cell") or 0) > 0)
    side = float(layer.property("cell"))
    point = layer.mapToScene(QPointF(0.5 * side, 0.5 * side))
    target = helpers.window_of(window, layer)
    helpers.APP.sendEvent(target, QMouseEvent(
        QEvent.MouseButtonPress, point, point, Qt.LeftButton, Qt.LeftButton,
        Qt.NoModifier))
    helpers.APP.processEvents()
    panel = helpers.find_item(window, "mapPanel")
    assert helpers.wait_for(lambda: panel.property("dragging") is True,
                            timeout=2.0), "长按没抓起这一格"
    return panel


def _point_at(monkeypatch, window, x, y, down=True):
    """把光标指到**逻辑坐标** (x, y)；`down` 控制左键还按着没有。

    真实现读的是**物理像素**（`_cursor_pos`），`controller.cursorState()` 会除回
    devicePixelRatio —— 所以这里按这台机器的 dpr 乘回去，和真机一致。
    """
    import chaita.ui.controller.monsters.drag as drag_mod
    scale = 1.0
    try:
        screen = window.screen()
        if screen is not None:
            scale = float(screen.devicePixelRatio()) or 1.0
    except Exception:
        scale = 1.0
    monkeypatch.setattr(drag_mod, "_cursor_pos",
                        lambda: (x * scale, y * scale))
    monkeypatch.setattr(drag_mod, "_cursor_down", lambda: down)


def _row_center(sheet, row):
    from PySide6.QtCore import QPointF
    box = row.mapToItem(None, QPointF(0, 0))
    return (sheet.x() + box.x() + row.width() / 2,
            sheet.y() + box.y() + row.height() / 2)


def test_dragging_a_cell_onto_an_item_row_records_the_coord(monkeypatch):
    """测什么：编辑模式下长按抓起一格 → 拖到「红宝石」那一行上松手 → 这一格记给红宝石。

    交互顺序：① 点「清单 ›」开这一层（自动进编辑）② 在大图 (1,1) 按住不动（起笔）
    ③ 光标移到红宝石那一行上 ④ 松开左键
    → 断言 `gridCells` 里多出一格 item/红宝石、这一行的数量变 1。
    """
    controller, engine, window = _open_sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 0,
         "icon": "gem_red"}])
    sheet = window.floorSheetOf("长安1")
    panel = _press_and_hold(window)

    row = helpers.find_all(window, "floorItemRow")[0]
    _point_at(monkeypatch, window, *_row_center(sheet, row), down=True)
    helpers.wait_for(lambda: False, timeout=0.2)          # 让轮询跑几帧
    assert panel.property("dragging") is True, "按着的时候不该结束"

    _point_at(monkeypatch, window, *_row_center(sheet, row), down=False)
    assert helpers.wait_for(lambda: panel.property("dragging") is False,
                            timeout=2.0), "松手之后拖拽没结束"

    cells = _cells(controller)
    assert [(c["kind"], c["name"]) for c in cells] == [("item", "红宝石")]
    rows = window.sheetItems("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 1, "数量应该跟着这一格变"


def test_dragging_a_cell_onto_a_monster_row_records_the_coord(monkeypatch):
    """测什么：抓一格拖到**怪**那一行上松手 → 这一格记给那只怪，数量变 1。

    交互顺序：① 点「清单 ›」开这一层（自动进编辑）② 在大图 (1,1) 按住不动（起笔）
    ③ 光标移到血蚊那一行上 ④ 松开左键 → 断言 `gridCells` 里是 monster/血蚊、
    `sheetMons[0].count == 1`。
    """
    controller, engine, window = _open_sheet()
    sheet = window.floorSheetOf("长安1")
    panel = _press_and_hold(window)

    row = helpers.find_all(window, "floorMonRow")[0]
    _point_at(monkeypatch, window, *_row_center(sheet, row), down=False)
    assert helpers.wait_for(lambda: panel.property("dragging") is False,
                            timeout=2.0)

    cells = _cells(controller)
    assert [(c["kind"], c["name"]) for c in cells] == [("monster", "血蚊")]
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 1


def test_releasing_the_drag_off_any_row_records_nothing(monkeypatch):
    """测什么：拖出去在空白处松手 → 什么都不记，底部提示"松开的地方没有行"。

    交互顺序：① 开「清单 ›」（自动进编辑）② 在 (1,1) 按住起笔 ③ 光标移到窗口左上角
    外面 ④ 松手 → 断言 `gridCells` 还是空、`mapHint` 有那句提示。
    """
    controller, engine, window = _open_sheet()
    sheet = window.floorSheetOf("长安1")
    panel = _press_and_hold(window)

    _point_at(monkeypatch, window, sheet.x() - 60, sheet.y() - 60, down=False)
    assert helpers.wait_for(lambda: panel.property("dragging") is False,
                            timeout=2.0)

    assert _cells(controller) == []
    assert "松开的地方没有行" in str(window.property("mapHint"))
