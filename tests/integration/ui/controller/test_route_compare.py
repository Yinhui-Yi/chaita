"""路线对比窗口集成测试：开窗 → 粘贴/拖入路线 → 每只怪的掉血 + 合计。

期望值**手算**（不拿 run_plan 自己比自己）：
  英雄 血 1000 / 攻 90 / 防 30；血蚊 1200 血 / 攻 60 / 防 20 / 带先攻。
  - 攻击 90：每回合 90-20=70 → ceil(1200/70)=18 回合 → 挨 17 下 ×30 + 先攻 30
    = 540；剩 460。
  - 先吃红宝石（攻 +1 → 91）：91-20=71 → ceil(1200/71)=17 回合 → 挨 16 下 ×30
    + 先攻 30 = 510；剩 490。
所以「先打血蚊再吃宝石」掉 540，「先吃宝石再打血蚊」掉 510 —— 正好拿来对比。
"""

import json

from ... import helpers


def _steps_route(monster_first):
    monster = {"kind": "monster", "name": "血蚊", "hp": 1200, "atk": 60,
               "def": 20, "count": 1,
               "skills": [{"name": "先攻", "code": "", "params": {}}]}
    gem = {"kind": "item", "name": "红宝石", "effect": "攻击力 +1",
           "icon": "gem_red", "count": 1}
    return {"steps": [monster, gem] if monster_first else [gem, monster]}


def _open():
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "0"}
    window.openCompare()
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
