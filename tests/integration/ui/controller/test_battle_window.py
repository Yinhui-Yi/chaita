"""伤害计算窗口集成测试：开窗 → 加怪/资源 → 计算 → 总掉血/剩血。

期望值**手算**（不拿 run_plan 自己比自己）：
  血蚊 1200 血 / 攻 60 / 防 20 / 带先攻，英雄 血 1000 / 攻 90 / 防 30。
  每回合打 90-20=70 → ceil(1200/70)=18 回合；挨 17 下 ×30 + 先攻 30 = 540；
  剩 460。吃红宝石（攻 +1）后攻 91：91-20=71 → ceil(1200/71)=17 回合；
  挨 16 下 ×30 + 先攻 30 = 510；剩 490。
"""

from ... import helpers


def _open():
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "0"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]
    window.openBattle()
    helpers.APP.processEvents()
    return controller, engine, window


def _monster(controller):
    return next(m for m in controller.battleMonsters()
                if m["name"] == "血蚊")


def test_battle_window_computes_monster_step():
    controller, engine, window = _open()
    window.battleAddMonster(_monster(controller))
    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()
    results = window.property("battlePlanResults")
    results = results.toVariant() if hasattr(results, "toVariant") else results
    assert results[0]["total_damage"] == 540
    assert results[0]["hp_after"] == 460
    assert helpers.find_item(window, "battlePlanDamage").property("text") \
        == "总掉血 540"
    assert helpers.find_item(window, "battlePlanLeftHp").property("text") \
        == "剩血 460"


def test_battle_window_item_raises_attack_for_next_monster():
    controller, engine, window = _open()
    # 红宝石的默认效果来自素材表，这里只锚定"它确实是 +1 攻"这一条数据来源
    gem = next(r for r in controller.battleItems() if r["name"] == "红宝石")
    assert "1" in gem["effect"]
    window.battleAddItem(gem)
    window.battleAddMonster(_monster(controller))
    window.battleComputePlan(0)
    helpers.APP.processEvents()
    results = window.property("battlePlanResults")
    results = results.toVariant() if hasattr(results, "toVariant") else results
    # 吃宝石攻 90→91，血蚊 17 回合 → 16×30 + 先攻 30 = 510
    assert results[0]["total_damage"] == 510
    assert results[0]["hp_after"] == 490
