"""routes 的存/改/删单元测试（`chaita/ui/controller/floors/routes.py`）。

真值来自规则：拖完路线按 grid 预填、备注可改、一格只留认识字段。
"""

from unittest.mock import Mock

from chaita.ui.controller.floors.routes import RoutesMixin


class FakeRoutes(RoutesMixin):
    def __init__(self, history, monsters=None):
        self._map_history = history
        self._monsters = monsters or []
        self.mapHistoryChanged = Mock()

    def _find_floor(self, floor_text):
        for index, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                return index
        return -1

    def battleMonsters(self):
        return self._monsters


def test_save_route_prefills_from_grid():
    monsters = [{"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
                 "skills": [{"name": "先攻", "code": "", "params": {}}],
                 "skillsText": "先攻"}]
    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]}}], monsters)
    index = c.saveRoute("1层", [{"row": 0, "col": 0}, {"row": 0, "col": 1}])
    cells = c._map_history[0]["routes"][index]["cells"]
    # 有内容的那格带上了手册里的数值
    assert cells[0]["kind"] == "monster"
    assert cells[0]["name"] == "血蚊"
    assert cells[0]["hp"] == "1200"
    assert cells[0]["atk"] == "60"
    assert cells[0]["def"] == "20"
    # 空的那格只有坐标，没有 kind
    assert "kind" not in cells[1]


def test_save_route_memo():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    index = c.saveRoute("1层", [{"row": 0, "col": 0}])
    assert c.saveRouteMemo("1层", index, "血 500 · 这里有个钥匙")
    assert c._map_history[0]["routes"][index]["memo"] == "血 500 · 这里有个钥匙"


def test_save_route_cell():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    index = c.saveRoute("1层", [{"row": 0, "col": 0}])
    assert c.saveRouteCell("1层", index, 0,
                           {"kind": "monster", "name": "血蚊",
                            "hp": 1200, "atk": 60, "def": 20, "count": 3})
    cell = c._map_history[0]["routes"][index]["cells"][0]
    assert cell["kind"] == "monster"
    assert cell["name"] == "血蚊"
    assert cell["count"] == 3


def test_remove_route():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    c.saveRoute("1层", [{"row": 0, "col": 0}])
    c.saveRoute("1层", [{"row": 1, "col": 1}])
    assert c.removeRoute("1层", 0)
    assert len(c._map_history[0]["routes"]) == 1


# ---- 边角：序号过期/空输入都不许炸 ----

def test_save_route_without_cells_or_floor():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    assert c.saveRoute("1层", []) == -1
    assert c.saveRoute("1层", [{"row": "x", "col": 1}]) == -1
    assert c.saveRoute("没有这层", [{"row": 0, "col": 0}]) == -1
    assert c._map_history[0].get("routes") is None


def test_save_route_caps_total_routes():
    from chaita.ui.controller.floors.routes import MAX_ROUTES
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    for i in range(MAX_ROUTES + 5):
        index = c.saveRoute("1层", [{"row": 0, "col": 0}])
        assert index == min(i + 1, MAX_ROUTES) - 1
    assert len(c._map_history[0]["routes"]) == MAX_ROUTES


def test_route_cells_bad_index_is_empty():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    c.saveRoute("1层", [{"row": 0, "col": 0}])
    assert c.routeCells("1层", 9) == []
    assert c.routeCells("1层", -1) == []
    assert c.routeCells("没有这层", 0) == []


def test_save_route_memo_clears_when_empty():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    index = c.saveRoute("1层", [{"row": 0, "col": 0}])
    c.saveRouteMemo("1层", index, "手写一句")
    assert c.saveRouteMemo("1层", index, "   ")
    assert "memo" not in c._map_history[0]["routes"][index]


def test_save_route_memo_flattens_newlines():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    index = c.saveRoute("1层", [{"row": 0, "col": 0}])
    c.saveRouteMemo("1层", index, "第一行\n第二行\r第三行")
    assert c._map_history[0]["routes"][index]["memo"] == "第一行 第二行 第三行"


def test_route_editors_reject_stale_indexes():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    index = c.saveRoute("1层", [{"row": 0, "col": 0}])

    assert c.saveRouteMemo("1层", 9, "x") is False
    assert c.removeRoute("1层", 9) is False
    assert c.removeRoute("没有这层", 0) is False
    assert c.saveRouteCell("1层", index, 9, {"kind": "monster",
                                             "name": "血蚊"}) is False
    assert c.saveRouteCell("1层", 9, 0, {"kind": "monster",
                                         "name": "血蚊"}) is False


# ---- 预填：只认怪 / 宝石 / 血瓶 ----

def test_route_items_keeps_only_gems_and_potions():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    c.battleItems = lambda: [
        {"name": "红宝石", "icon": "gem_red"},
        {"name": "血瓶", "icon": "potion_red"},
        {"name": "黄钥匙", "icon": "xinxin2_yellowKey"},
        {"name": "铁剑", "icon": "xinxin2_sword1"}]

    names = [row["name"] for row in c.routeItems()]

    assert names == ["红宝石", "血瓶"]          # 钥匙/武器不进路线链


def test_map_content_skips_broken_cells():
    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": "x", "col": 1, "kind": "monster", "name": "血蚊"},   # 坐标坏
        {"row": 1, "col": 1, "kind": "door", "name": "门"},           # 不认识的种类
        {"row": 2, "col": 2, "kind": "monster", "name": "  "},        # 没名字
        "不是 dict",
        {"row": 3, "col": 3, "kind": "item", "name": "红宝石"}]}}])

    found = c._map_content(c._map_history[0])

    assert list(found) == [(3, 3)]
    assert found[(3, 3)] == {"kind": "item", "name": "红宝石", "effect": ""}


def test_map_content_keeps_item_effect():
    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": 0, "col": 0, "kind": "item", "name": "血瓶",
         "effect": "体力 +300"}]}}])
    assert c._map_content(c._map_history[0])[(0, 0)]["effect"] == "体力 +300"


def test_route_prefill_skips_non_gem_items(monkeypatch):
    """格子记的是钥匙：链上只留坐标，不填内容（用户："非怪和宝石血瓶不需要显示"）。"""
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "xinxin2_yellowKey")
    monkeypatch.setattr(ii, "is_gem", lambda stem: False)
    monkeypatch.setattr(ii, "is_potion", lambda stem, name="": False)
    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": 0, "col": 0, "kind": "item", "name": "黄钥匙"}]}}])

    cells = c._with_map_content(c._map_history[0], [{"row": 0, "col": 0}])

    assert "kind" not in cells[0]
    assert "name" not in cells[0]


def test_route_prefill_fills_gem_icon_and_effect(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "gem_red")
    monkeypatch.setattr(ii, "is_gem", lambda stem: True)
    monkeypatch.setattr(ii, "is_potion", lambda stem, name="": False)
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "攻击力 +1")
    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": 0, "col": 0, "kind": "item", "name": "红宝石"}]}}])

    cells = c._with_map_content(c._map_history[0], [{"row": 0, "col": 0}])

    assert cells[0]["kind"] == "item"
    assert cells[0]["icon"] == "gem_red"
    assert cells[0]["effect"] == "攻击力 +1"


def test_route_prefill_keeps_cells_when_no_grid():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    cells = c._with_map_content(c._map_history[0], [{"row": 0, "col": 0}])
    assert cells == [{"row": 0, "col": 0}]


def test_clean_fill_drops_bad_skills():
    from chaita.ui.controller.floors.routes import _clean_fill
    out = _clean_fill({"kind": "monster", "name": "血蚊",
                       "skills": ["不是 dict", {"name": "  "},
                                  {"name": "先攻", "code": "7",
                                   "params": {"a": 1}}],
                       "effect": ""})
    assert out["skills"] == [{"name": "先攻", "code": "7", "params": {"a": 1}}]
    assert "effect" not in out
