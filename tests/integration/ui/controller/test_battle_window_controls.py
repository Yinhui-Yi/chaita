"""伤害计算窗口的按钮接线（真点击）：加一行 / 删一行 / 清空 / 选怪 / 选资源 / 改勇者数值。

`test_battle_window.py` 只管"算得对不对"（数值真值），这一份只管**控件接对没接对**：
点「＋ 新的计算」是不是真多一行、点 ✕ 删的是不是那一行、问号菜单里选怪/切资源页
是不是真把那一步加进这一行。

真值手推：血蚊 1200 血 / 攻 60 / 防 20 / 先攻，勇者 血 1000 / 攻 90 / 防 30 →
每回合 70 → 18 回合 → 挨 17×30 + 先攻 30 = 540，走完剩 460。
"""

from ... import helpers


def _open():
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]
    window.openBattle()
    helpers.APP.processEvents()
    return controller, engine, window


def _plans(window):
    value = window.property("battlePlans")
    return value.toVariant() if hasattr(value, "toVariant") else value


def _pick_row(window, name, tries=12):
    """下拉里那一行；**等它画出来**（菜单刚打开时列表还是空的）。"""
    for _ in range(tries):
        for row in helpers.find_all(window, "battlePickRow"):
            if any(name in text for text in helpers.texts_of(row)):
                return row
        helpers.wait_for(lambda: helpers.find_all(window, "battlePickRow") != [],
                         timeout=0.4)
    raise AssertionError("伤害计算的下拉里没有「%s」：%s"
                         % (name, [helpers.texts_of(r)
                                   for r in helpers.find_all(window,
                                                             "battlePickRow")]))


def _menu_ready(window):
    return (str(window.property("battleMenu") or "") != ""
            and helpers.find_all(window, "battlePickRow") != [])


def _open_menu(window):
    """开门器：点「＋」直到菜单真的打开**并且列出条目**。"""
    for _ in range(5):
        if _menu_ready(window):
            return True
        if str(window.property("battleMenu") or "") == "":
            helpers.click_item(window, helpers.find_item(window, "battleRowAsk"))
        helpers.wait_for(lambda: _menu_ready(window), timeout=0.5)
    return _menu_ready(window)


def _add_step(window, name, plan=0):
    """往第 `plan` 行加一步，并等到真的加进去（加不上就直接报错，别默默往下走）。"""
    assert _open_menu(window), "点「＋」没把选择菜单打开"
    for _ in range(5):
        helpers.click_item(window, _pick_row(window, name))
        if helpers.wait_for(lambda: _has_step(window, plan), timeout=0.4):
            return True
    raise AssertionError("选了「%s」但这一步没进计划" % name)


def _has_step(window, plan=0):
    try:
        return bool(_steps(window, plan))
    except (IndexError, KeyError, TypeError):
        return False


def _steps(window, plan=0):
    plans = window.property("battlePlans")
    plans = plans.toVariant() if hasattr(plans, "toVariant") else plans
    return plans[plan]["steps"]


def test_add_row_button_creates_second_plan():
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleAddRow"))
    helpers.APP.processEvents()

    rows = window.property("battleRows")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
    assert len(rows) == 2
    assert _plans(window)[1]["steps"] == []


def test_delete_row_button_removes_that_plan():
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleAddRow"))
    helpers.APP.processEvents()

    # 删第二行（两行都是空的，删哪行结果都一样，这里删最后一个 ✕）
    helpers.click_item(window, helpers.find_all(window, "battleRowDelete")[-1])
    helpers.APP.processEvents()

    rows = window.property("battleRows")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
    assert len(rows) == 1


def test_clear_button_empties_every_row():
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleAddRow"))
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "battleClear"))
    helpers.APP.processEvents()

    rows = window.property("battleRows")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
    assert rows == []


def test_pick_monster_from_menu_then_run_computes():
    controller, engine, window = _open()
    # 行尾的问号 = 往这一行最后加一步
    _add_step(window, "血蚊")
    assert [s["name"] for s in _steps(window)] == ["血蚊"]

    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    results = window.property("battlePlanResults")
    results = results.toVariant() if hasattr(results, "toVariant") else results
    assert results[0]["total_damage"] == 540
    assert results[0]["hp_after"] == 460


def test_item_tab_adds_resource_step():
    controller, engine, window = _open()
    assert _open_menu(window)
    helpers.click_item(window, helpers.find_item(window, "battleTabItem"))
    assert str(window.property("battlePickTab")) == "item"

    helpers.click_item(window, _pick_row(window, "红宝石"))

    steps = _steps(window)
    assert [s["kind"] for s in steps] == ["item"]
    assert steps[0]["name"] == "红宝石"


def test_hero_field_edit_updates_hero():
    controller, engine, window = _open()
    field = helpers.find_item(window, "battleHero_hpField")
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", "1500")
    helpers.APP.processEvents()

    hero = window.property("battleHero")
    hero = hero.toVariant() if hasattr(hero, "toVariant") else hero
    assert hero["hp"] == 1500


def test_close_button_closes_window():
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleClose"))
    helpers.APP.processEvents()

    value = window.property("battleWindow")
    value = value.toQObject() if hasattr(value, "toQObject") else value
    assert value is None


# ---- 读取人物 / 粘贴路线 / 往中间插一步 / 每格掉血的显示 ----

def test_read_button_reads_person(monkeypatch):
    import numpy as np

    from chaita.game import read as game_read
    from chaita.game import towers
    controller, engine, window = _open()
    helpers.fake_game_window(monkeypatch, towers.H5_MOTA.process)
    img = np.zeros((20, 20, 3), np.uint8)
    monkeypatch.setattr(game_read, "grab_window", lambda p: img)
    monkeypatch.setattr(game_read, "read_person",
                        lambda image, api_key=None: {"hp": "842", "atk": "13"})
    import chaita.ui.controller.status as status_mod
    monkeypatch.setattr(status_mod, "_api_key", lambda: "k")

    helpers.click_item(window, helpers.find_item(window, "battleRead"))
    # 结果是通过 uiCall（队列连接）排回界面线程的：等它落地，别只看一次 processEvents
    helpers.wait_for(lambda: controller._last_status.get("hp") == "842",
                     timeout=2.0)

    assert controller._last_status["hp"] == "842"
    assert controller._last_status["atk"] == "13"


def test_paste_button_adds_plan_from_clipboard(monkeypatch):
    import json
    helpers.fake_clipboard(monkeypatch)        # 别动用户真剪贴板
    controller, engine, window = _open()
    controller.clipboardCopy(json.dumps({"steps": [
        {"kind": "monster", "name": "血蚊", "hp": 1200, "atk": 60, "def": 20,
         "icon": "", "count": 1, "skills": []}]}))

    helpers.click_item(window, helpers.find_item(window, "battlePaste"))
    helpers.APP.processEvents()

    plans = _plans(window)
    # 窗口本来就带着一行空的；粘贴是**再开一行**（用户："路线要能复制，可以粘贴到伤害计算界面"）
    assert plans[0]["steps"] == []
    assert [step["name"] for step in plans[1]["steps"]] == ["血蚊"]


def test_arrow_inserts_step_before_that_one():
    controller, engine, window = _open()
    # 先摆两步：血蚊 + 铁卫
    controller._monsters.append({"name": "铁卫", "hp": "900", "atk": "50",
                                 "def": "30"})
    _add_step(window, "血蚊")
    _add_step(window, "铁卫")
    assert [s["name"] for s in _steps(window)] == ["血蚊", "铁卫"]

    # 点第 2 格前面那个箭头 → 插在它前面
    arrows = helpers.find_all(window, "battleRowArrow")
    helpers.click_item(window, arrows[1])
    helpers.click_item(window, _pick_row(window, "血蚊"))

    assert [s["name"] for s in _steps(window)] == \
        ["血蚊", "血蚊", "铁卫"]


def test_damage_label_shows_after_compute():
    controller, engine, window = _open()
    _add_step(window, "血蚊")
    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    text = helpers.find_item(window, "battleRowDamage").property("text")
    assert "540" in str(text)                  # 每回合 70 → 18 回合 → 540


# ---- 两处"状态的显示"：空列表提示、没算进去的技能 ----

def test_empty_hint_shows_after_clearing_plans():
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleClear"))
    helpers.APP.processEvents()

    empty = helpers.find_item(window, "battleEmpty")
    assert empty is not None and empty.isVisible()
    assert "新的计算" in str(empty.property("text"))


def test_unhandled_skills_are_listed_after_compute():
    """算不进去的技能要明说（不能装作算过了）—— 塞一个表里没有的技能名。"""
    controller, engine, window = _open()
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "神秘技能", "code": "", "params": {}}]}]
    _add_step(window, "血蚊")
    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    note = helpers.find_item(window, "battleUnhandled")
    assert note is not None and note.isVisible()
    assert "没算进去" in str(note.property("text"))


# ---- 两个页签 + 行尾那个箭头 ----

def test_pick_tab_switches_back_to_monsters():
    controller, engine, window = _open()
    assert _open_menu(window)
    helpers.click_item(window, helpers.find_item(window, "battleTabItem"))
    assert str(window.property("battlePickTab")) == "item"

    helpers.click_item(window, helpers.find_item(window, "battleTabMonster"))
    assert str(window.property("battlePickTab")) == "monster"
    # 回到怪物页之后，列表里又只有怪（没有资源）
    rows = helpers.find_all(window, "battlePickRow")
    assert rows
    assert any("血蚊" in text for row in rows
               for text in helpers.texts_of(row))


def test_row_end_arrow_opens_the_menu():
    controller, engine, window = _open()
    assert str(window.property("battleMenu")) == ""

    helpers.click_item(window, helpers.find_item(window, "battleRowArrowEnd"))

    assert str(window.property("battleMenu")) != ""
    assert int(window.property("battleMenuPlan")) == 0

