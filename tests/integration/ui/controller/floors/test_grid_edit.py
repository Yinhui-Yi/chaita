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


def _open_sheet(items=None, mons=None, extra_floor=""):
    """摆好这一层，点「清单 ›」开窗（开清单会自动进编辑模式）。

    `extra_floor` 给了就再摆一层空的（测"切层之后编辑模式还跟不跟"）。
    """
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": mons or [{"name": "血蚊", "count": 1}],
        "items": items or [],
        "grid": {"cells": []},
        "routes": []}]
    if extra_floor:
        controller._map_history.insert(0, {
            "floor": str(extra_floor), "url": "",
            "mons": [{"name": "铁卫", "count": 1}], "items": [],
            "grid": {"cells": []}, "routes": []})
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    assert helpers.wait_for(
        lambda: helpers.find_item(window, "mapSheet") is not None), \
        "地图那一栏没出来"
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    current = str(window.property("mapFloor"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf(current) is not None), "清单没打开"
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
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊",
         "manual": True},
        {"row": 0, "col": 1, "kind": "monster", "name": "血蚊",
         "manual": True}]
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
    helpers.show_tab(window, "item")
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


# ---- 编辑模式**按下**就抓起一格，拖到「这一层」某一行上松手 ----

def _cell_spot(window, row=0, col=0):
    """某一格中心：`(场景坐标, 逻辑屏幕坐标)`。

    场景坐标用来往窗口里送鼠标事件，逻辑屏幕坐标用来骗 `cursorState()` —— 两者
    必须指的是同一格，不然"按下抓的是哪一格"和"松手在哪一格"就对不上了。
    """
    from PySide6.QtCore import QPointF
    layer = helpers.find_item(window, "routeLayer")
    side = float(layer.property("cell"))
    scene = layer.mapToScene(QPointF((col + 0.5) * side, (row + 0.5) * side))
    return scene, (window.x() + scene.x(), window.y() + scene.y())


def _press_cell(monkeypatch, window, row=0, col=0, modifiers=None):
    """在大图某一格上按下（编辑模式 → 按下这一下就抓起这一格，不等长按）。

    **必须先把光标桩成"就在这一格、左键还按着"**：合成的按下事件不会真按住鼠标，
    而拖拽是靠轮询光标发现松手的 —— 不桩的话第一帧就判成"已经松手"，拖拽当场结束
    （跑全量时就会看到 `cell_drag_end miss <桌面光标>` 这种）。
    """
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QMouseEvent
    layer = helpers.find_item(window, "routeLayer")
    helpers.wait_for(lambda: float(layer.property("cell") or 0) > 0)
    point, spot = _cell_spot(window, row, col)
    _point_at(monkeypatch, window, spot[0], spot[1], down=True)
    helpers.APP.sendEvent(helpers.window_of(window, layer), QMouseEvent(
        QEvent.MouseButtonPress, point, point, Qt.LeftButton, Qt.LeftButton,
        Qt.NoModifier if modifiers is None else modifiers))
    helpers.APP.processEvents()
    panel = helpers.find_item(window, "mapPanel")
    assert helpers.wait_for(lambda: panel.property("dragging") is True,
                            timeout=2.0), "按下没抓起这一格"
    return panel


def _release_cell(monkeypatch, window, row=0, col=0, modifiers=None):
    """在某一格上真松手（`tapped` 走的是真鼠标松开事件，别只桩光标）。"""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QMouseEvent
    layer = helpers.find_item(window, "routeLayer")
    point, spot = _cell_spot(window, row, col)
    helpers.APP.sendEvent(helpers.window_of(window, layer), QMouseEvent(
        QEvent.MouseButtonRelease, point, point, Qt.LeftButton, Qt.NoButton,
        Qt.NoModifier if modifiers is None else modifiers))
    helpers.APP.processEvents()
    _point_at(monkeypatch, window, spot[0], spot[1], down=False)


def _release_at(monkeypatch, window, x, y):
    """光标挪到逻辑坐标 (x, y) 再松开左键（松手由 `cursorState` 轮询发现）。"""
    _point_at(monkeypatch, window, x, y, down=True)
    helpers.wait_for(lambda: False, timeout=0.1)
    _point_at(monkeypatch, window, x, y, down=False)
    panel = helpers.find_item(window, "mapPanel")
    assert helpers.wait_for(lambda: panel.property("dragging") is False,
                            timeout=2.0), "松手之后拖拽没结束"
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
    """测什么：编辑模式下抓起一格 → 拖到「红宝石」那一行上松手 → 这一格记给红宝石。

    交互顺序：① 点「清单 ›」开这一层（自动进编辑）② 在大图 (1,1) 按下（抓起这一格）
    ③ 光标移到红宝石那一行上 ④ 松开左键
    → 断言 `gridCells` 里多出一格 item/红宝石、这一行的数量变 1。
    """
    controller, engine, window = _open_sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 0,
         "icon": "gem_red"}])
    sheet = window.floorSheetOf("长安1")
    helpers.show_tab(window, "item")
    panel = _press_cell(monkeypatch, window)

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

    交互顺序：① 点「清单 ›」开这一层（自动进编辑）② 在大图 (1,1) 按下（抓起这一格）
    ③ 光标移到血蚊那一行上 ④ 松开左键 → 断言 `gridCells` 里是 monster/血蚊、
    `sheetMons[0].count == 1`。
    """
    controller, engine, window = _open_sheet()
    sheet = window.floorSheetOf("长安1")
    panel = _press_cell(monkeypatch, window)

    row = helpers.find_all(window, "floorMonRow")[0]
    _point_at(monkeypatch, window, *_row_center(sheet, row), down=True)
    # 拖着经过这一行：胶囊写「放到这里」（窗口自己轮询光标认出是哪一行）
    assert helpers.wait_for(
        lambda: helpers.texts_of(
            helpers.find_item(window, "floorMonPos")) == ["放到这里"],
        timeout=2.0), "拖着格子经过这一行，它没亮起来"
    _point_at(monkeypatch, window, *_row_center(sheet, row), down=False)
    assert helpers.wait_for(lambda: panel.property("dragging") is False,
                            timeout=2.0)
    assert helpers.texts_of(helpers.find_item(window, "floorMonPos")) == ["1 格"], \
        "松手之后高亮没收掉"

    cells = _cells(controller)
    assert [(c["kind"], c["name"]) for c in cells] == [("monster", "血蚊")]
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 1


def test_pressing_and_dragging_at_once_records_the_coord(monkeypatch):
    """测什么：**按下就立刻拖**（中间不等任何时间）也要记上坐标。

    这条是用户报的那个 bug 的回归：抓格子以前挂在"按住 350ms 不动"上，一按下就
    移动会被手势自己取消（`onPositionChanged` 里 `moved > 6px` → 长按 stop），
    松手什么都不发生、连一行日志都没有（用户 2026-10-31："无法通过拖动给清单里的
    东西添加坐标"）。所以这里按下之后**一帧都不等**，直接挪到行上松手。

    交互顺序：① 开「清单 ›」（自动进编辑）② 在 (1,1) 按下并立刻把光标挪到血蚊行
    ③ 松手 → 断言这一格记给了血蚊。
    """
    controller, engine, window = _open_sheet()
    sheet = window.floorSheetOf("长安1")
    _press_cell(monkeypatch, window)                    # 按下（不等长按）

    row = helpers.find_all(window, "floorMonRow")[0]
    _release_at(monkeypatch, window, *_row_center(sheet, row))

    assert [(c["kind"], c["name"]) for c in _cells(controller)] == [
        ("monster", "血蚊")]
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 1, "数量应该跟着这一格变"


def test_clicking_a_cell_without_moving_selects_it_without_a_warning(monkeypatch):
    """测什么：**点一下不拖** = 选中这一格，不记坐标、也不弹"松开的地方没有行"。

    按下就抓起之后，"点一下"和"拖出去没命中"只差"光标有没有离开那一格"，这条盯住
    前半段：松手还在原格 → `gridPicked` 设上、grid 还是空、底部不出现那句红字。

    交互顺序：① 开「清单 ›」② 在 (1,1) 按下 → 原地松手。
    """
    controller, engine, window = _open_sheet()
    _press_cell(monkeypatch, window)       # 按下 (1,1)（光标就桩在这一格上、按着）
    _release_cell(monkeypatch, window)     # 原地真松手：`tapped` 走真鼠标松开事件
    panel = helpers.find_item(window, "mapPanel")
    assert helpers.wait_for(lambda: panel.property("dragging") is False,
                            timeout=2.0), "松手之后拖拽没结束"

    assert _cells(controller) == [], "点一下不该记坐标"
    picked = window.property("gridPicked") or {}
    picked = picked.toVariant() if hasattr(picked, "toVariant") else picked
    assert (int(picked.get("row", -1)), int(picked.get("col", -1))) == (0, 0), \
        "点一下应该选中这一格"
    assert "没有行" not in str(window.property("mapHint")), \
        "点一下不该弹'松开的地方没有行'"


def test_one_drag_records_every_ctrl_selected_cell(monkeypatch):
    """测什么：Ctrl 勾了 2 格 → 拖其中一格到怪那一行 → **两格都记上**（数量 2）。

    这是用户报的"Ctrl 多选怎么没了"的回归：勾选以前只画个框，落格只记抓着的那一格，
    落完还把勾选清掉。规则：**这一拖记 = 勾上的 + 抓着的**。

    交互顺序：① 开「清单 ›」② Ctrl+点 (1,1)、(1,2) 勾上 ③ 在 (1,1) 按下拖到血蚊行
    ④ 松手 → 断言 grid 里两格、血蚊数量 2、勾选清空。
    """
    from PySide6.QtCore import Qt
    controller, engine, window = _open_sheet(mons=[{"name": "血蚊", "count": 0}])
    sheet = window.floorSheetOf("长安1")

    for col in (0, 1):
        _press_cell(monkeypatch, window, 0, col, Qt.ControlModifier)
        _release_cell(monkeypatch, window, 0, col, Qt.ControlModifier)
    multi = window.property("gridMulti")
    multi = multi.toVariant() if hasattr(multi, "toVariant") else multi
    assert [(int(c["row"]), int(c["col"])) for c in (multi or [])] == \
        [(0, 0), (0, 1)], "Ctrl+点没勾上"

    _press_cell(monkeypatch, window, 0, 0)              # 抓着勾过的那一格拖
    row = helpers.find_all(window, "floorMonRow")[0]
    _release_at(monkeypatch, window, *_row_center(sheet, row))

    assert sorted((int(c["row"]), int(c["col"]))
                  for c in _cells(controller)) == [(0, 0), (0, 1)]
    assert all(c["name"] == "血蚊" for c in _cells(controller))
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 2, "两格都记上，数量应该变 2"
    multi = window.property("gridMulti")
    multi = multi.toVariant() if hasattr(multi, "toVariant") else multi
    assert not multi, "落完格子勾选该清空"


def test_dragging_an_unselected_cell_adds_it_to_the_selection(monkeypatch):
    """测什么：勾了 (1,1)、去拖没勾的 (2,2) → **两格都记**（这一拖 = 勾上的 + 抓着的）。

    规则只有一条，别出现"拖一下勾选就没了"或者"勾了 3 格只记 1 格"这种半截行为：
    抓起的那一格没勾也会并进这一拖，勾着的格子一直算数。
    """
    from PySide6.QtCore import Qt
    controller, engine, window = _open_sheet(mons=[{"name": "血蚊", "count": 0}])
    sheet = window.floorSheetOf("长安1")

    _press_cell(monkeypatch, window, 0, 0, Qt.ControlModifier)
    _release_cell(monkeypatch, window, 0, 0, Qt.ControlModifier)   # 勾上 (1,1)

    _press_cell(monkeypatch, window, 1, 1)                # 去拖没勾的 (2,2)
    row = helpers.find_all(window, "floorMonRow")[0]
    _release_at(monkeypatch, window, *_row_center(sheet, row))

    cells = _cells(controller)
    assert sorted((int(c["row"]), int(c["col"])) for c in cells) == [(0, 0), (1, 1)]


def test_clicking_one_cell_then_ctrl_clicking_more_records_all_of_them(monkeypatch):
    """测什么：**先点一格、再 Ctrl 点后面两格** → 拖其中任意一格，三格都记上。

    用户 2026-10-31："我先选中一格再按ctrl按后面两格，第一格的坐标丢失"。
    原因：普通点选以前只写 `gridPicked`（右键菜单的目标），不进"要一起记的一批"，
    拖的时候就被漏掉了。现在点选 = 选中（集合就这一格），Ctrl+点往里加，
    拖 = 这一批 + 抓着的那一格。

    交互顺序：① 点 (1,1) ② Ctrl+点 (1,2)、(1,3) ③ 抓着 (1,2) 拖到血蚊行松手
    → 断言三格都进了 grid、血蚊数量 3。
    """
    from PySide6.QtCore import Qt
    controller, engine, window = _open_sheet(mons=[{"name": "血蚊", "count": 0}])
    sheet = window.floorSheetOf("长安1")

    _press_cell(monkeypatch, window, 0, 0)                # ① 普通点选
    _release_cell(monkeypatch, window, 0, 0)
    for col in (1, 2):                                    # ② Ctrl 加成多选
        _press_cell(monkeypatch, window, 0, col, Qt.ControlModifier)
        _release_cell(monkeypatch, window, 0, col, Qt.ControlModifier)
    multi = window.property("gridMulti")
    multi = multi.toVariant() if hasattr(multi, "toVariant") else multi
    assert sorted((int(c["row"]), int(c["col"])) for c in (multi or [])) == \
        [(0, 0), (0, 1), (0, 2)], "点选 + Ctrl 点应该勾成三格"

    _press_cell(monkeypatch, window, 0, 1)                # ③ 抓着中间那格拖
    row = helpers.find_all(window, "floorMonRow")[0]
    _release_at(monkeypatch, window, *_row_center(sheet, row))

    assert sorted((int(c["row"]), int(c["col"]))
                  for c in _cells(controller)) == [(0, 0), (0, 1), (0, 2)]
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["count"] == 3


def test_right_clicking_a_cell_keeps_the_multi_selection(monkeypatch):
    """测什么：勾了几格之后右键看一格坐标，**勾选不能没**（右键只挪菜单目标）。

    以前右键也走"点选"，一右键就把多选清掉了。
    """
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    controller, engine, window = _open_sheet()
    for col in (0, 1):
        _press_cell(monkeypatch, window, 0, col, Qt.ControlModifier)
        _release_cell(monkeypatch, window, 0, col, Qt.ControlModifier)

    layer = helpers.find_item(window, "routeLayer")
    point = layer.mapToScene(QPointF(3.5 * float(layer.property("cell")),
                                     3.5 * float(layer.property("cell"))))
    target = helpers.window_of(window, layer)
    for kind, button in ((QEvent.MouseButtonPress, Qt.RightButton),
                         (QEvent.MouseButtonRelease, Qt.NoButton)):
        helpers.APP.sendEvent(target, QMouseEvent(
            kind, point, point, Qt.RightButton, button, Qt.NoModifier))
        helpers.APP.processEvents()

    multi = window.property("gridMulti")
    multi = multi.toVariant() if hasattr(multi, "toVariant") else multi
    assert sorted((int(c["row"]), int(c["col"])) for c in (multi or [])) == \
        [(0, 0), (0, 1)], "右键不该清掉勾选"
    picked = window.property("gridPicked")
    picked = picked.toVariant() if hasattr(picked, "toVariant") else picked
    assert (int(picked.get("row", -1)), int(picked.get("col", -1))) == (3, 3), \
        "右键应该把菜单目标挪到那一格"


def test_edit_mode_follows_a_floor_switch(monkeypatch):
    """测什么：编辑模式下在侧栏切层 → 新的一层**仍然是编辑模式**（按下抓格子，不是画路线）。

    `panel.editing` 要求 `gridEditFloor === mapFloor`，切层后不同步就会变假，
    手势退回"画路线"，表现就是拖不动且没有任何提示。

    交互顺序：① 点「清单 ›」开长安1（自动进编辑）② 点侧栏那一行切到长安2
    ③ 在新层的大图 (1,1) 上按下 → 断言 `dragging` 为真（抓格子）、
    路线层没有起笔。
    """
    controller, engine, window = _open_sheet(extra_floor="长安2")
    rows = helpers.find_all(window, "floorRailRow")
    assert len(rows) == 2
    # 上面那行是最高的层（长安2）
    helpers.click_item(window, rows[0])
    helpers.APP.processEvents()
    assert window.property("mapFloor") == "长安2"
    assert window.property("gridEditFloor") == "长安2", "编辑模式没跟着切层"
    assert helpers.find_item(window, "mapPanel").property("editing") is True

    panel = _press_cell(monkeypatch, window)
    assert panel.property("dragging") is True
    assert helpers.find_item(window, "routeLayer").property("editing") is False


def test_releasing_the_drag_off_any_row_records_nothing(monkeypatch):
    """测什么：拖出去在空白处松手 → 什么都不记，底部提示"松开的地方没有行"。

    交互顺序：① 开「清单 ›」（自动进编辑）② 在 (1,1) 按下抓起这一格 ③ 光标移到窗口
    左上角外面 ④ 松手 → 断言 `gridCells` 还是空、`mapHint` 有那句提示（松手不在原格，
    所以不是"点了一下"，要提示）。
    """
    controller, engine, window = _open_sheet()
    sheet = window.floorSheetOf("长安1")
    panel = _press_cell(monkeypatch, window)

    _point_at(monkeypatch, window, sheet.x() - 60, sheet.y() - 60, down=False)
    assert helpers.wait_for(lambda: panel.property("dragging") is False,
                            timeout=2.0)

    assert _cells(controller) == []
    assert "松开的地方没有行" in str(window.property("mapHint"))


# ---- 「刷新」不许动手动改过的东西 ----

def test_refreshing_keeps_the_coords_and_numbers_the_user_set(monkeypatch):
    """测什么：拖好的坐标 + 改过的数量，整层重读（刷新）之后**原样还在**。

    这条是用户 2026-10-31 的三条规则一起验（真 Controller + 真 QML）：
      · 手动定过的（拖的格子、改过的行）一个字段都不动；
      · 清单从格子里推，数量 = 占几格；
      · 这次读到的东西里，清单没有的才加行。

    交互顺序：① 开「清单 ›」 ② 把 (1,1) 拖到血蚊那一行 ③ 把血蚊数量改成 9
    ④ 跑一次刷新（AI 说这层有 2 格血蚊、还有一只新怪铁卫）→ 断言用户标的那一格
    还在、血蚊数量还是 9、铁卫按格子数加进来（2）。
    """
    controller, engine, window = _open_sheet(mons=[{"name": "血蚊", "count": 0}])
    sheet = window.floorSheetOf("长安1")

    _press_cell(monkeypatch, window)                       # 抓起 (1,1)
    row = helpers.find_all(window, "floorMonRow")[0]
    _release_at(monkeypatch, window, *_row_center(sheet, row))
    controller.saveFloorMonsterField("长安1", 0, "count", "9")
    helpers.APP.processEvents()

    # 刷新：AI 这次说血蚊在另外两格、铁卫在 (5,5)、(5,6)
    controller._apply_scan("长安1", {"cells": [
        {"row": 3, "col": 3, "kind": "monster", "name": "血蚊"},
        {"row": 4, "col": 4, "kind": "monster", "name": "血蚊"},
        {"row": 5, "col": 5, "kind": "monster", "name": "铁卫"},
        {"row": 5, "col": 6, "kind": "monster", "name": "铁卫"}]})
    helpers.APP.processEvents()

    # 用户拖的那一格原样留着（AI 这次没读到它，也没被清掉）；AI 读到的位置并进来
    positions = controller.gridPositions("长安1", "血蚊")
    assert {"row": 0, "col": 0} in positions, "用户标的坐标不许丢"
    assert len(positions) == 3, "用户那一格 + AI 这次的两格"
    mons = window.sheetMons("长安1")
    mons = mons.toVariant() if hasattr(mons, "toVariant") else list(mons or [])
    by_name = {row["name"]: row for row in mons}
    assert by_name["血蚊"]["count"] == 9, "用户改过的数量不许被格数覆盖"
    # 新读到的怪按格子数加进来
    assert by_name["铁卫"]["count"] == 2
