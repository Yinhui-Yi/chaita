"""路线对比窗口集成测试：开窗 → 粘贴/拖入路线 → 每只怪的掉血 + 合计 + 定位。

期望值**手算**（不拿 run_plan 自己比自己）：
  英雄 血 1000 / 攻 90 / 防 30；血蚊 1200 血 / 攻 60 / 防 20 / 带先攻。
  - 攻击 90：每回合 90-20=70 → ceil(1200/70)=18 回合 → 挨 17 下 ×30 + 先攻 30
    = 540；剩 460。
  - 先吃红宝石（攻 +1 → 91）：91-20=71 → ceil(1200/71)=17 回合 → 挨 16 下 ×30
    + 先攻 30 = 510；剩 490。
所以「先打血蚊再吃宝石」掉 540，「先吃宝石再打血蚊」掉 510 —— 正好拿来对比。

表的前面那一列**不写怪名**（用户："不要写怪物名字！！！用缩略图和坐标！！"）：
缩略图 + 「第几行第几列」；点一行就去那一层的小窗里把这一格圈出来
（用户："最好点击后会在地图内高亮"）。
"""

import json

from PySide6.QtCore import QPointF

from ... import helpers

FLOOR = "长安1"


def _steps_route(monster_first):
    monster = {"kind": "monster", "name": "血蚊", "hp": 1200, "atk": 60,
               "def": 20, "count": 1,
               "skills": [{"name": "先攻", "code": "", "params": {}}]}
    gem = {"kind": "item", "name": "红宝石", "effect": "攻击力 +1",
           "icon": "gem_red", "count": 1}
    return {"steps": [monster, gem] if monster_first else [gem, monster]}


def _spot_route(icon="file:///tmp/red_slime.png", row=5, col=5):
    """带**坐标和缩略图**的一条路线（「复制」写出去的就是这一份）。"""
    monster = {"kind": "monster", "name": "血蚊", "hp": 1200, "atk": 60,
               "def": 20, "count": 1,
               "skills": [{"name": "先攻", "code": "", "params": {}}],
               "icon": icon, "floor": FLOOR, "row": row, "col": col}
    return {"steps": [monster]}


def _open():
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                              "mdef": "0"}
    window.openCompare()
    helpers.APP.processEvents()
    return controller, engine, window


def _open_with_floor():
    """带上这一层（`长安1`）的记录：点一行要能开它的小窗、圈出格子。"""
    controller, engine, window = _open()
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]
    controller._map_history = [{
        "floor": FLOOR, "url": "",
        "mons": [{"name": "血蚊", "count": 1}],
        "items": [],
        "grid": {"cells": [{"row": 5, "col": 5, "kind": "monster",
                            "name": "血蚊"}]}}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    return controller, engine, window


def _routes(window):
    value = window.property("compareRoutes")
    return value.toVariant() if hasattr(value, "toVariant") else list(value or [])


def _rows(window):
    value = window.compareRows()
    return value.toVariant() if hasattr(value, "toVariant") else value


def _totals(window):
    value = window.compareTotals()
    return value.toVariant() if hasattr(value, "toVariant") else value


def _floors(window):
    value = window.property("floorWindows")
    return value.toVariant() if hasattr(value, "toVariant") else value


def _paste(window, board, payload):
    board.setText(json.dumps(payload))
    window.comparePaste()
    helpers.APP.processEvents()


def test_compare_window_opens_from_the_nav_bar():
    controller, engine, window = _open()
    assert window.property("compareWindow") is not None
    # 入口在主窗口导航条上（伤害计算右边）
    assert helpers.find_item(window, "compareOpen") is not None
    assert helpers.find_item(window, "battleOpen") is not None
    # 一条路线都没有时给提示，而不是一片空白
    empty = helpers.find_item(window, "compareEmpty")
    assert empty is not None and empty.isVisible()


def test_compare_paste_one_route_shows_per_monster_damage(monkeypatch):
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open()
    _paste(window, board, _steps_route(True))

    routes = _routes(window)
    assert len(routes) == 1
    rows = _rows(window)
    assert [row["name"] for row in rows] == ["血蚊"]
    assert rows[0]["damages"][0]["damage"] == 540
    totals = _totals(window)
    assert totals[0]["total"] == 540
    assert totals[0]["hp"] == 460


def test_compare_two_routes_compare_the_same_monster(monkeypatch):
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open()
    _paste(window, board, _steps_route(True))     # 先打怪再吃宝石 → 540
    _paste(window, board, _steps_route(False))    # 先吃宝石再打怪 → 510

    assert len(_routes(window)) == 2
    rows = _rows(window)
    assert [row["name"] for row in rows] == ["血蚊"]
    assert [one["damage"] for one in rows[0]["damages"]] == [540, 510]
    totals = _totals(window)
    assert [one["total"] for one in totals] == [540, 510]
    assert [one["hp"] for one in totals] == [460, 490]


def test_compare_drop_imports_a_route(monkeypatch):
    """拖进来的路线走的是和粘贴同一种 JSON（拖到 DropArea 上松手真能进来）。"""
    controller, engine, window = _open()
    drop = helpers.find_item(window, "compareDrop")
    assert drop is not None, "路线对比窗口要有一个拖放目标区"
    helpers.drop_text(window, drop, "application/x-route-json",
                      json.dumps(_steps_route(True)))

    assert len(_routes(window)) == 1
    assert _rows(window)[0]["damages"][0]["damage"] == 540


def test_compare_drop_ignores_other_mime_types(monkeypatch):
    controller, engine, window = _open()
    drop = helpers.find_item(window, "compareDrop")
    helpers.drop_text(window, drop, "text/plain", "随便一段话")
    assert _routes(window) == []


def test_compare_clear_and_remove(monkeypatch):
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open()
    _paste(window, board, _steps_route(True))
    _paste(window, board, _steps_route(False))
    assert len(_routes(window)) == 2

    window.compareRemove(0)
    helpers.APP.processEvents()
    assert len(_routes(window)) == 1
    assert _totals(window)[0]["total"] == 510

    window.compareClear()
    helpers.APP.processEvents()
    assert _routes(window) == []
    empty = helpers.find_item(window, "compareEmpty")
    assert empty is not None and empty.isVisible()


def test_compare_ignores_clipboard_that_is_not_a_route(monkeypatch):
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open()
    board.setText("这是一段随便的话，不是路线 JSON")
    window.comparePaste()
    helpers.APP.processEvents()
    assert _routes(window) == []


# ---- 坐标 / 缩略图 / 点一行去地图上圈格 ----


def test_compare_row_carries_the_thumbnail_and_the_coord_not_the_name(monkeypatch):
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _spot_route())

    row = _rows(window)[0]
    assert (row["floor"], row["row"], row["col"]) == (FLOOR, 5, 5)
    assert row["icon"].endswith("red_slime.png")
    # 表上画出来的是缩略图 + 坐标（行列从 1 数：第 6 行第 6 列）
    texts = []
    for item in helpers.find_all(window, "compareRow"):
        texts.extend(helpers.texts_of(item))
    assert any("6,6" in text for text in texts), texts
    assert not any("血蚊" in text for text in texts), texts
    # 缩略图真的挂上了那张图
    thumb = helpers.find_item(window, "compareThumbImage")
    assert thumb is not None and thumb.property("source") == row["icon"]


def test_compare_click_a_row_opens_that_floor_and_highlights_the_cell():
    controller, engine, window = _open_with_floor()
    # 直接摆一条带坐标的路线（不走剪贴板，剪贴板是另一件事，上面测过）
    window.compareAdd(_spot_route()["steps"], "路线1")
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "compareRowClick"))
    assert window.property("mapHiFloor") == FLOOR
    assert window.property("mapHiRow") == 5
    assert window.property("mapHiCol") == 5
    # 这一层的小窗开出来了，格子上那个圈是可见的
    assert helpers.wait_for(lambda: FLOOR in list(_floors(window))), _floors(window)
    assert helpers.wait_for(
        lambda: helpers.find_item(window, "floorCellHighlight") is not None)
    ring = helpers.find_item(window, "floorCellHighlight")
    assert ring is not None and ring.isVisible()


def test_compare_highlight_needs_a_coord():
    """老路线（「复制」里还没坐标）点一行什么都不做：不开窗、不圈格。"""
    controller, engine, window = _open_with_floor()
    window.compareAdd(_steps_route(True)["steps"], "路线1")
    helpers.APP.processEvents()

    row = _rows(window)[0]
    assert (row["row"], row["col"]) == (-1, -1)
    assert window.compareHighlight(row) is False
    assert window.property("mapHiFloor") == ""
    assert list(_floors(window)) == []


def test_compare_highlight_moves_with_the_next_click(monkeypatch):
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _spot_route())
    _paste(window, board, _spot_route(row=3, col=9))
    helpers.APP.processEvents()

    rows = _rows(window)
    assert len(rows) == 1, "同一只怪在同一条线上只占一行"
    assert window.compareHighlight(rows[0]) is True
    assert (window.property("mapHiRow"), window.property("mapHiCol")) == (5, 5)
    # 关掉对比窗就把那个圈清掉，别留在地图上
    window.closeCompare()
    helpers.APP.processEvents()
    assert window.property("mapHiFloor") == ""
    assert window.property("mapHiRow") == -1


def test_route_copy_then_compare_paste_keeps_the_coord(monkeypatch):
    """用户那条真路：路线链「复制」→ 对比窗「粘贴」→ 表上有坐标、点得动。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    window.storeRoute(FLOOR, [{"row": 5, "col": 5}])   # 拖出来的路线（自动预填这一格）
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "routeCopy"))
    assert "血蚊" in board.text(), board.text()
    window.closeRoute(helpers.route_window(window).property("ctx"))
    window.comparePaste()
    helpers.APP.processEvents()

    row = _rows(window)[0]
    assert (row["floor"], row["row"], row["col"]) == (FLOOR, 5, 5)
    assert window.compareHighlight(row) is True


def test_compare_columns_line_up_with_the_header(monkeypatch):
    """每条路线的数字必须正对着表头那一列（差 4px 都算没对齐）。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _spot_route())
    _paste(window, board, _spot_route(row=3, col=9))

    heads = helpers.find_all(window, "compareColName")
    values = helpers.find_all(window, "compareDamage")
    assert len(heads) == 2 and len(values) == 2
    # Repeater 的行/列要先走完布局，否则 x 还是 0（第一次跑就栽在这上面）
    assert helpers.wait_for(lambda: all(item.x() > 0 for item in heads)), \
        [item.x() for item in heads]
    for head, value in zip(heads, values):
        left = head.mapToScene(QPointF(0, 0)).x()
        right = value.mapToScene(QPointF(0, 0)).x()
        assert abs(left - right) < 0.5, (left, right)
