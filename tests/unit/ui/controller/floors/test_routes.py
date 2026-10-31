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


# ---- 链上亲手改过的那一格优先（用户 2026-10-31）----

def _one_cell_route():
    """一格路线，且这一层的地图记录里同一坐标写着"血蚊"。"""
    monsters = [{"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"}]
    history = [{"floor": "1层",
                "grid": {"cells": [{"row": 0, "col": 0, "kind": "monster",
                                    "name": "血蚊"}]}}]
    c = FakeRoutes(history, monsters)
    index = c.saveRoute("1层", [{"row": 0, "col": 0}])
    return c, index


def test_manual_cell_beats_the_map_record():
    """链上改一格之后，显示的是链上那份，不是地图记录那份。"""
    c, index = _one_cell_route()
    assert c.routeCells("1层", index)[0]["name"] == "血蚊"

    assert c.saveRouteCell("1层", index, 0,
                           {"kind": "item", "name": "红宝石",
                            "effect": "攻击力 +1"})
    cell = c.routeCells("1层", index)[0]
    assert (cell["kind"], cell["name"]) == ("item", "红宝石")


def test_manual_cell_does_not_touch_the_map_record():
    """改链上那一格不许动这一层的地图记录。"""
    c, index = _one_cell_route()
    before = [dict(cell) for cell in c._map_history[0]["grid"]["cells"]]

    c.saveRouteCell("1层", index, 0, {"kind": "item", "name": "红宝石"})

    assert c._map_history[0]["grid"]["cells"] == before


def test_manual_cell_does_not_touch_other_routes():
    """同层另一条路线的同一格还是照地图记录显示。"""
    c, index = _one_cell_route()
    other = c.saveRoute("1层", [{"row": 0, "col": 0}])

    c.saveRouteCell("1层", index, 0, {"kind": "item", "name": "红宝石"})

    assert c.routeCells("1层", other)[0]["name"] == "血蚊"


def test_clearing_a_cell_sticks_even_if_the_map_record_has_something():
    """链上把一格清空 → 就是空的，不会被地图记录又填回来。"""
    c, index = _one_cell_route()
    assert c.saveRouteCell("1层", index, 0, {})

    cell = c.routeCells("1层", index)[0]
    assert not cell.get("kind")
    assert not cell.get("name")


def test_untouched_cell_still_follows_the_map_record():
    """没亲手改过的格子仍然跟着地图记录实时变（原来那条规矩不变）。"""
    c, index = _one_cell_route()
    c._map_history[0]["grid"]["cells"][0]["name"] = "铁卫"
    # 换成手册里也有的怪，链上跟着变
    c._monsters = [{"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    assert c.routeCells("1层", index)[0]["name"] == "铁卫"


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


# ---- 预填：怪 / 宝石 / 武器 / 防具 / 血瓶 ----

def test_route_items_keeps_gems_weapons_armor_potions():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    c.battleItems = lambda: [
        {"name": "红宝石", "icon": "gem_red"},
        {"name": "血瓶", "icon": "potion_red"},
        {"name": "黄钥匙", "icon": "key_yellow"},
        {"name": "铁剑", "icon": "sword"},
        {"name": "铁盾", "icon": "shield"}]

    names = [row["name"] for row in c.routeItems()]

    assert names == ["红宝石", "血瓶", "铁剑", "铁盾"]  # 钥匙不进路线链


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


def test_route_prefill_skips_keys(monkeypatch):
    """格子记的是钥匙：链上只留坐标（钥匙和掉血无关）。"""
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "key_yellow")

    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": 0, "col": 0, "kind": "item", "name": "黄钥匙"}]}}])

    cells = c._with_map_content(c._map_history[0], [{"row": 0, "col": 0}])

    assert "kind" not in cells[0]
    assert "name" not in cells[0]


def test_route_prefill_fills_gem_icon_and_effect(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "gem_red")
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "攻击力 +1")
    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": 0, "col": 0, "kind": "item", "name": "红宝石"}]}}])

    cells = c._with_map_content(c._map_history[0], [{"row": 0, "col": 0}])

    assert cells[0]["kind"] == "item"
    assert cells[0]["icon"] == "gem_red"
    assert cells[0]["effect"] == "攻击力 +1"


def test_route_prefill_fills_weapon(monkeypatch):
    """格子记的是武器（铁剑）：要进路线链，带图标和默认效果。"""
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "sword")
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "攻击力 +0")
    c = FakeRoutes([{"floor": "1层", "grid": {"cells": [
        {"row": 0, "col": 0, "kind": "item", "name": "铁剑"}]}}])

    cells = c._with_map_content(c._map_history[0], [{"row": 0, "col": 0}])

    assert cells[0]["kind"] == "item"
    assert cells[0]["icon"] == "sword"
    assert cells[0]["effect"] == "攻击力 +0"


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

# ---- 跨层路线：每格记着它画在哪一层 ----

def test_clean_cells_keeps_floor():
    from chaita.ui.controller.floors.routes import _clean_cells
    cells = _clean_cells([{"row": 1, "col": 2, "floor": "1层"},
                          {"row": 3, "col": 4}])
    assert cells == [{"row": 1, "col": 2, "floor": "1层"}, {"row": 3, "col": 4}]


def test_route_prefill_uses_each_cell_own_floor(monkeypatch):
    """某格标的层不是路线起始层：内容从**那一层**的 grid 取，不是起始层。"""
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "gem_red")
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "攻击力 +1")
    c = FakeRoutes([
        {"floor": "1层", "grid": {"cells": [
            {"row": 0, "col": 0, "kind": "item", "name": "红宝石"}]}},
        {"floor": "2层", "grid": {"cells": [
            {"row": 0, "col": 0, "kind": "item", "name": "蓝宝石"}]}}])

    cells = c._with_map_content(c._map_history[0], [
        {"row": 0, "col": 0, "floor": "1层"},
        {"row": 0, "col": 0, "floor": "2层"}])

    assert cells[0]["name"] == "红宝石"
    assert cells[1]["name"] == "蓝宝石"


def test_route_save_keeps_floor_of_each_cell():
    c = FakeRoutes([{"floor": "1层", "grid": {}}])
    index = c.saveRoute("1层", [{"row": 0, "col": 0, "floor": "1层"},
                                {"row": 0, "col": 1, "floor": "2层"}])
    stored = c._map_history[0]["routes"][index]["cells"]
    assert [one.get("floor") for one in stored] == ["1层", "2层"]
