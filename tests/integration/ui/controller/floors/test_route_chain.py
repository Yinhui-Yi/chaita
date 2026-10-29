"""路线链集成测试：拖路线 → 摆链 → 计算 → 总掉血/剩血 → 备注（计算实时 + 手写）。

期望值**手算**（不拿 run_plan 自己比自己）：
  血蚊 1200 血 / 攻 60 / 防 20 / 带先攻，英雄 血 1000 / 攻 90 / 防 30。
  每回合打 90-20=70 → ceil(1200/70)=18 回合；
  它倒下那回合不还手 → 挨 17 下 ×(60-30)=30 = 510，先攻再 +30 = 540；
  走完剩 1000-540=460。
"""

from .... import helpers


def _make_route():
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": [{"name": "血蚊", "count": 1}],
        "items": [],
        "grid": {"cells": [{"row": 0, "col": 0, "kind": "monster",
                            "name": "血蚊"}]}}]
    controller.mapHistoryChanged.emit()
    # 松手生成路线（storeRoute 只存路径 + 打开链，不再写死的备注）
    window.storeRoute("长安1", [{"row": 0, "col": 0}])
    helpers.APP.processEvents()
    return controller, engine, window


def test_route_chain_computes_damage_and_total():
    controller, engine, window = _make_route()
    helpers.click_item(window, helpers.find_item(window, "routeRun"))
    helpers.APP.processEvents()
    result = window.property("routeResult")
    result = result.toVariant() if hasattr(result, "toVariant") else result
    assert result["total_damage"] == 540
    assert result["hp_after"] == 460
    # 总掉血 / 剩血 写在链右边
    assert helpers.find_item(window, "routeTotalDamage").property("text") \
        == "总掉血 540"
    assert helpers.find_item(window, "routeLeftHp").property("text") \
        == "剩血 460"


def test_route_computed_stats_are_live_not_saved_as_memo():
    controller, engine, window = _make_route()
    routes = controller._map_history[0]["routes"]
    assert len(routes) == 1
    # 备注不再自动写计算值（计算那部分是界面按当前格子实时算、只读显示）
    assert "memo" not in routes[0]
    assert window.routeStatsFor("长安1", 0) \
        == "血 460 · 攻 90 · 防 30 · 魔防 10"


def test_route_cells_reflect_current_grid_edits():
    controller, engine, window = _make_route()
    # 用户后来在编辑模式把 (0,0) 这一格改成别的怪
    controller.assignGridCell("长安1", 0, 0, "monster", "铁卫")
    helpers.APP.processEvents()
    # 路线链按坐标实时查 grid：现在摆的是铁卫，不是创建时的血蚊
    cells = controller.routeCells("长安1", 0)
    assert cells[0]["name"] == "铁卫"
