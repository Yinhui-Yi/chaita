"""路线对比窗口（**集成测试**，只点界面上的东西）。

期望值**手算**（不拿 run_plan 自己比自己）：
  英雄 血 1000 / 攻 90 / 防 30；血蚊 1200 血 / 攻 60 / 防 20 / 带先攻。
  - 攻击 90：每回合 90-20=70 → ceil(1200/70)=18 回合 → 挨 17 下 ×30 + 先攻 30 = 540；剩 460
  - 先吃红宝石（攻 +1 → 91）：91-20=71 → ceil(1200/71)=17 回合 → 挨 16 下 ×30 + 先攻 30
    = 510；剩 490
所以「先打血蚊再吃宝石」掉 540，「先吃宝石再打血蚊」掉 510。

标准见 `tests/integration/README.md`。驱动一律是：点导航条按钮开窗、点「粘贴」按钮、
往拖放区真发拖放事件、点表上的行、点「清空」/关闭。剪贴板是外部边界，用替身。

**不符合标准、已经删掉的**：
  · `test_compare_highlight_needs_a_coord` —— 直调 `compareAdd()` + `compareHighlight()`
  · `test_compare_highlight_moves_with_the_next_click` —— 直调 `compareHighlight()`（点击那条
    已经并进 `test_closing_the_window_clears_the_highlight`）
  · `test_compare_clear_and_remove` —— `compareRemove()/compareClear()` 直调；「清空」改成点按钮
    保留，「删一条」没有界面上能点的入口，**现在没人覆盖**
  · `test_route_copy_then_compare_paste_keeps_the_coord` —— 用 `window.storeRoute()` 直调摆数据 +
    `comparePaste()` 直调；这条"路线链复制 → 对比窗粘贴"的整链**现在没人覆盖**
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


def _open_with_floor():
    """起真 Controller + QML，点导航条上的对比入口开窗，并摆好这一层的记录。"""
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "0"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]
    controller._map_history = [{
        "floor": FLOOR, "url": "",
        "mons": [{"name": "血蚊", "count": 1}],
        "items": [],
        "grid": {"cells": [{"row": 5, "col": 5, "kind": "monster",
                            "name": "血蚊"}]},
        "routes": []}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    # 用户入口：导航条上那个「对比」按钮
    helpers.click_item(window, helpers.find_item(window, "compareOpen"))
    assert helpers.wait_for(
        lambda: window.property("compareWindow") is not None), "对比窗没开出来"
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


def _paste(window, board, payload):
    """真操作：把 JSON 放进剪贴板（替身）→ 点对比窗上的「粘贴」。"""
    board.setText(json.dumps(payload))
    helpers.click_item(window, helpers.find_item(window, "comparePaste"))
    helpers.APP.processEvents()


def test_compare_opens_from_the_nav_bar_button():
    """测什么：导航条上那个对比按钮能开出对比窗，一条路线都没有时显示提示而不是空白。

    交互顺序：① 点导航条上的对比按钮 → 断言对比窗开出来、空态提示可见。"""
    controller, engine, window = _open_with_floor()
    assert helpers.find_item(window, "compareOpen") is not None
    empty = helpers.find_item(window, "compareEmpty")
    assert empty is not None and empty.isVisible()


def test_paste_button_shows_per_monster_damage_and_totals(monkeypatch):
    """测什么：点「粘贴」把剪贴板里那条路线放进表里，每只怪的掉血和合计都对。

    交互顺序：① 剪贴板里放一条路线 JSON ② 点对比窗「粘贴」
    ③ 断言表身那一行的掉血 540、合计那行 540 / 剩 460。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _steps_route(True))

    assert len(_routes(window)) == 1
    rows = _rows(window)
    assert [row["name"] for row in rows] == ["血蚊"]
    assert rows[0]["damages"][0]["damage"] == 540
    totals = _totals(window)
    assert totals[0]["total"] == 540
    assert totals[0]["hp"] == 460


def test_two_routes_compare_the_same_monster(monkeypatch):
    """测什么：粘两条顺序不同的路线 → 同一只怪并到一行，两个数并排对比。

    交互顺序：① 粘第一条（先打怪再吃宝石）② 再粘第二条（先吃宝石再打怪）
    ③ 断言同一只怪并成一行，两个数是 540 / 510。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _steps_route(True))
    _paste(window, board, _steps_route(False))

    assert len(_routes(window)) == 2
    rows = _rows(window)
    assert [row["name"] for row in rows] == ["血蚊"]
    assert [one["damage"] for one in rows[0]["damages"]] == [540, 510]
    assert [one["total"] for one in _totals(window)] == [540, 510]
    assert [one["hp"] for one in _totals(window)] == [460, 490]


def test_drop_imports_a_route():
    """测什么：把路线 JSON 拖到对比窗的拖放区上松手，真的能进来。

    交互顺序：① 把路线 JSON 真拖到对比窗的拖放区上松手
    ② 断言表里多了一条、掉血 540。"""
    controller, engine, window = _open_with_floor()
    drop = helpers.find_item(window, "compareDrop")
    assert drop is not None, "对比窗要有一个拖放目标区"
    helpers.drop_text(window, drop, "application/x-route-json",
                      json.dumps(_steps_route(True)))

    assert len(_routes(window)) == 1
    assert _rows(window)[0]["damages"][0]["damage"] == 540


def test_drop_ignores_other_mime_types():
    """测什么：拖进来的不是路线（text/plain）就什么也不加。

    交互顺序：① 把一段普通文字按 `text/plain` 真拖到拖放区 → 断言表里什么都没加。"""
    controller, engine, window = _open_with_floor()
    drop = helpers.find_item(window, "compareDrop")
    helpers.drop_text(window, drop, "text/plain", "随便一段话")
    assert _routes(window) == []


def test_paste_ignores_clipboard_that_is_not_a_route(monkeypatch):
    """测什么：剪贴板里是普通文字时点「粘贴」，表里什么也不加。

    交互顺序：① 剪贴板里放一段普通文字 ② 点「粘贴」→ 断言表里什么都没加。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    board.setText("这是一段随便的话，不是路线 JSON")
    helpers.click_item(window, helpers.find_item(window, "comparePaste"))
    helpers.APP.processEvents()
    assert _routes(window) == []


def test_clear_button_empties_the_table(monkeypatch):
    """测什么：点「清空」把所有路线去掉，回到"还没有路线"的提示。

    交互顺序：① 点「粘贴」加一条 ② 点「清空」→ 断言表空了、空态提示又出现。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _steps_route(True))
    assert len(_routes(window)) == 1

    helpers.click_item(window, helpers.find_item(window, "compareClear"))
    helpers.APP.processEvents()
    assert _routes(window) == []
    empty = helpers.find_item(window, "compareEmpty")
    assert empty is not None and empty.isVisible()


def test_row_shows_thumbnail_and_coord_not_the_name(monkeypatch):
    """测什么：表上那一列画的是**缩略图 + 坐标**，不写怪名（用户："不要写怪物名字！
    用缩略图和坐标！"）。

    交互顺序：① 点「粘贴」放进一条带坐标的路线 ② 读表身第一列
    → 断言写的是「6,6」和缩略图、**不写怪名**。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _spot_route())

    row = _rows(window)[0]
    assert (row["floor"], row["row"], row["col"]) == (FLOOR, 5, 5)
    assert row["icon"].endswith("red_slime.png")

    texts = []
    for item in helpers.find_all(window, "compareRow"):
        texts.extend(helpers.texts_of(item))
    assert any("6,6" in text for text in texts), texts
    assert not any("血蚊" in text for text in texts), texts

    thumb = helpers.find_item(window, "compareThumbImage")
    assert thumb is not None and thumb.property("source") == row["icon"]


def test_clicking_a_row_highlights_that_cell_on_the_map(monkeypatch):
    """测什么：点表上一行 → 主界面地图切到那一层、把那一格圈出来。

    交互顺序：① 点「粘贴」 ② 点表身那一行 → 断言主界面地图切到那一层、
    那一格被圈出来（`floorCellHighlight` 可见）。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _spot_route())

    helpers.click_item(window, helpers.find_item(window, "compareRowClick"))
    assert window.property("mapHiFloor") == FLOOR
    assert (window.property("mapHiRow"), window.property("mapHiCol")) == (5, 5)
    assert window.property("mapCollapsed") is False
    assert window.property("mapFloor") == FLOOR
    ring = helpers.find_item(window, "floorCellHighlight")
    assert ring is not None and ring.isVisible()


def test_closing_the_compare_window_clears_the_highlight(monkeypatch):
    """测什么：关掉对比窗，地图上那个圈也清掉（不留一个孤零零的高亮）。

    交互顺序：① 点「粘贴」 ② 点表身那一行（地图圈出来）③ 点对比窗关闭
    → 断言地图上那个圈被清掉。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _open_with_floor()
    _paste(window, board, _spot_route())
    helpers.click_item(window, helpers.find_item(window, "compareRowClick"))
    assert window.property("mapHiFloor") == FLOOR

    helpers.click_item(window, helpers.find_item(window, "compareClose"))
    helpers.APP.processEvents()
    assert window.property("mapHiFloor") == ""
    assert window.property("mapHiRow") == -1


def test_columns_line_up_with_the_header(monkeypatch):
    """测什么：每条路线的数字正对着表头那一列（差 4px 也算没对齐，踩过这个坑）。

    交互顺序：① 点「粘贴」两次放两条路线 → 量表头与数字的 x 坐标
    → 断言每条路线的数字正对着它那一列。"""
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
