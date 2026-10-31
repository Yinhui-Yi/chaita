"""路线链：**算得对不对 + 链按当前格子实时查**（集成测试，真点击）。

期望值**手算**（不拿 run_plan 自己比自己）：
  血蚊 1200 血 / 攻 60 / 防 20 / 带先攻，英雄 血 1000 / 攻 90 / 防 30。
  每回合打 90-20=70 → ceil(1200/70)=18 回合；它倒下那回合不还手 →
  挨 17 下 ×(60-30)=30 = 510，先攻再 +30 = 540；走完剩 1000-540=460。

标准见 `tests/integration/README.md`。起点那条路线用 `window.storeRoute()` 造（README 里
给的豁免：真人造路线是地图长按拖，已在 `test_cross_floor_*.py` 覆盖），之后全部点界面：
链窗口的「计算」、编辑模式把格子拖到清单某一行上。断言读公开属性
（`window.routeResult / routeTotalDamage / routeLeftHp`、`controller.routeCells`）。

**改掉的**：`test_route_cells_reflect_current_grid_edits` 原来直调
`controller.assignGridCell(...)`，现在改成真 drop 事件（把格子拖到「铁卫」那一行上）。
"""

from .... import helpers


def _make_route(mons=("血蚊",)):
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "0"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": [{"name": name, "count": 1} for name in mons],
        "items": [],
        "grid": {"cells": [{"row": 0, "col": 0, "kind": "monster",
                            "name": mons[0]}]},
        "routes": []}]
    controller.mapHistoryChanged.emit()
    controller.monstersChanged.emit()
    # 松手生成路线（storeRoute 只存路径 + 打开链，不再写死的备注）
    window.storeRoute("长安1", [{"row": 0, "col": 0}])
    helpers.APP.processEvents()
    return controller, engine, window


def test_route_chain_computes_damage_and_total():
    """测什么：点「计算」→ 掉血 540、剩血 460，链右边写出总掉血/剩血。

    交互顺序：① 地图上松手生成的那条路线（链窗口已经开着）② 点「计算」
    → 断言 `routeResult` 的 total_damage/hp_after，以及右边的两处文字。
    """
    controller, engine, window = _make_route()
    helpers.click_item(window, helpers.find_item(window, "routeRun"))
    helpers.APP.processEvents()
    result = window.property("routeResult")
    result = result.toVariant() if hasattr(result, "toVariant") else result
    assert result["total_damage"] == 540
    assert result["hp_after"] == 460
    assert helpers.find_item(window, "routeTotalDamage").property("text") \
        == "总掉血 540"
    assert helpers.find_item(window, "routeLeftHp").property("text") \
        == "剩血 460"


def test_route_stats_are_computed_live_not_stored_as_memo():
    """测什么：那条路线的备注里**没有**自动写进去的计算值，数值是界面实时算的。

    交互顺序：① 生成路线（链窗口开着）→ 断言存下来的路线只有格子、没有 memo，
    而 `routeStatsFor` 现在算出来的就是"血 460…"（会随人物数值变，不是存下来的）。
    """
    controller, engine, window = _make_route()
    rows = controller.mapHistory
    rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
    routes = rows[0]["routes"]
    assert len(routes) == 1
    assert "memo" not in routes[0], "计算值不该被写进备注"
    assert window.routeStatsFor("长安1", 0) == "血 460 · 攻 90 · 防 30 · 魔防 0"


def test_route_cells_follow_the_current_grid():
    """测什么：路线链按坐标**实时查**这一层的格子：格子改成铁卫，链上就显示铁卫。

    交互顺序：① 生成路线（链上是血蚊）② 点「清单 ›」开这一层（自动进编辑模式）
    ③ 把 (1,1) 这一格拖到「铁卫」那一行上松手 ④ 断言 `routeCells` 里那一格变成了铁卫。
    """
    controller, engine, window = _make_route(mons=("血蚊", "铁卫"))
    assert str(controller.routeCells("长安1", 0)[0]["name"]) == "血蚊"

    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("长安1") is not None), "清单没打开"
    assert window.property("gridEditOn") is True, "开清单应该自动进编辑模式"

    rows = helpers.find_all(window, "floorMonRow")
    assert len(rows) == 2
    helpers.drop_cells(window, rows[1], {"row": 0, "col": 0})
    helpers.APP.processEvents()

    cells = controller.routeCells("长安1", 0)
    assert str(cells[0]["name"]) == "铁卫"
