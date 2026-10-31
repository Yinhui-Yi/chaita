"""伤害计算窗口：**数值真值**（集成测试，只点界面上的东西）。

期望值**手算**（不拿 run_plan 自己比自己）：
  血蚊 1200 血 / 攻 60 / 防 20 / 带先攻，英雄 血 1000 / 攻 90 / 防 30。
  每回合打 90-20=70 → ceil(1200/70)=18 回合；挨 17 下 ×30 + 先攻 30 = 540；剩 460。
  吃红宝石（攻 +1）后攻 91：91-20=71 → ceil(1200/71)=17 回合；
  挨 16 下 ×30 + 先攻 30 = 510；剩 490。

标准见 `tests/integration/README.md`。驱动：点导航条 ⚔ 开窗 → 行尾问号 → 菜单里选（含切
「资源」页）→ 点「计算」。断言读公开属性（`window.battlePlanResults`）和行上的文字。

**改掉的**：原来 2 条直调 `window.battleAddMonster / battleAddItem / battleComputePlan`，
现在全走真点击。
"""

from ... import helpers


def _open():
    """起真 Controller + QML，点导航条 ⚔ 开伤害计算窗口。"""
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "0"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]
    controller.statusTextChanged.emit()
    controller.monstersChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "battleOpen"))
    assert helpers.wait_for(
        lambda: window.property("battleWindow") is not None), "伤害计算窗口没打开"
    helpers.APP.processEvents()
    return controller, engine, window


def _pick_row(window, name, tries=12):
    """下拉里那一行；等它画出来（菜单刚打开时列表还是空的）。"""
    for _ in range(tries):
        for row in helpers.find_all(window, "battlePickRow"):
            if any(name in text for text in helpers.texts_of(row)):
                return row
        helpers.wait_for(lambda: helpers.find_all(window, "battlePickRow") != [],
                         timeout=0.4)
    raise AssertionError("下拉里没有「%s」" % name)


def _menu_ready(window):
    return (str(window.property("battleMenu") or "") != ""
            and helpers.find_all(window, "battlePickRow") != [])


def _add_step(window, name, tab=None):
    """点行尾问号 → （可选）切页 → 选一项，等到它真进计划。"""
    for _ in range(5):
        if _menu_ready(window):
            break
        helpers.click_item(window, helpers.find_item(window, "battleRowAsk"))
        helpers.wait_for(lambda: _menu_ready(window), timeout=0.5)
    assert _menu_ready(window), "点问号没把选择菜单打开"
    if tab is not None:
        helpers.click_item(window, helpers.find_item(window, tab))
        helpers.APP.processEvents()
    for _ in range(5):
        helpers.click_item(window, _pick_row(window, name))
        if helpers.wait_for(lambda: _steps(window), timeout=0.4):
            return
    raise AssertionError("选了「%s」但这一步没进计划" % name)


def _steps(window, plan=0):
    plans = window.property("battlePlans")
    plans = plans.toVariant() if hasattr(plans, "toVariant") else plans
    return plans[plan]["steps"]


def _results(window):
    value = window.property("battlePlanResults")
    return value.toVariant() if hasattr(value, "toVariant") else value


def test_monster_step_computes_540_and_leaves_460():
    """测什么：一行里只有血蚊，点「计算」→ 掉血 540、剩血 460（行上也写出来）。

    交互顺序：① 导航条 ⚔ 开窗 ② 行尾问号 → 菜单选「血蚊」 ③ 点「计算」
    → 断言 `battlePlanResults` 和行上的「总掉血 / 剩血」两处文字。
    """
    controller, engine, window = _open()
    _add_step(window, "血蚊")

    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    results = _results(window)
    assert results[0]["total_damage"] == 540
    assert results[0]["hp_after"] == 460
    assert helpers.find_item(window, "battlePlanDamage").property("text") \
        == "总掉血 540"
    assert helpers.find_item(window, "battlePlanLeftHp").property("text") \
        == "剩血 460"


def test_item_then_monster_computes_510():
    """测什么：先吃红宝石（攻 +1）再打血蚊 → 掉血 510、剩血 490。

    交互顺序：① 导航条 ⚔ 开窗 ② 问号 → 切「资源」页 → 选「红宝石」
    ③ 问号 → 选「血蚊」 ④ 点「计算」→ 断言 510 / 490。
    """
    controller, engine, window = _open()
    _add_step(window, "红宝石", tab="battleTabItem")
    _add_step(window, "血蚊")

    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    results = _results(window)
    # 吃宝石攻 90→91，血蚊 17 回合 → 16×30 + 先攻 30 = 510
    assert results[0]["total_damage"] == 510
    assert results[0]["hp_after"] == 490
