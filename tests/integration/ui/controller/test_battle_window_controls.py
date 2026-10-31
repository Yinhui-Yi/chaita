"""伤害计算窗口的按钮接线（**集成测试**，只点界面上的东西）。

`test_battle_window.py` 只管"算得对不对"（数值真值），这一份只管**控件接对没接对**：
「＋ 新的计算」是不是真多一行、✕ 删的是不是那一行、问号菜单里选怪/切资源页是不是真把
那一步加进这一行、勇者数值改了有没有生效、读取人物/粘贴路线/插一步、每格掉血显示。

真值手推：血蚊 1200 血 / 攻 60 / 防 20 / 先攻，勇者 血 1000 / 攻 90 / 防 30 →
每回合 70 → 18 回合 → 挨 17×30 + 先攻 30 = 540，走完剩 460。

标准见 `tests/integration/README.md`。驱动：点导航条的 ⚔ 开窗，之后全部点窗口里的控件；
抓图/模型/剪贴板这三样是外部边界，用替身。起点数据（怪物库、勇者数值）直接摆。

**改掉的**：原来 `_open()` 直调 `window.openBattle()`（Slot），现在点导航条按钮；
`test_read_button_reads_person` 的断言从 `controller._last_status` 换成 `statusData`；
粘贴那条的剪贴板内容从 `controller.clipboardCopy()`（Slot）改成直接写替身剪贴板。
"""

from ... import helpers


def _open():
    """起真 Controller + QML，点导航条的 ⚔ 把伤害计算窗口打开。"""
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
        lambda: window.property("battleWindow") is not None), \
        "伤害计算窗口没打开"
    helpers.APP.processEvents()
    return controller, engine, window


def _plans(window):
    value = window.property("battlePlans")
    return value.toVariant() if hasattr(value, "toVariant") else value


def _rows(window):
    value = window.property("battleRows")
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
    """开门器：点行尾那个问号，直到菜单真的打开**并列出条目**。"""
    for _ in range(5):
        if _menu_ready(window):
            return True
        if str(window.property("battleMenu") or "") == "":
            helpers.click_item(window, helpers.find_item(window, "battleRowAsk"))
        helpers.wait_for(lambda: _menu_ready(window), timeout=0.5)
    return _menu_ready(window)


def _add_step(window, name, plan=0):
    """往第 `plan` 行加一步，并等到真的加进去（加不上就报错，别默默往下走）。"""
    assert _open_menu(window), "点问号没把选择菜单打开"
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
    """测什么：点「＋ 新的计算」→ 多出第二行，且是空的。

    走过的界面：导航条 ⚔ → 伤害计算窗口 →「＋ 新的计算」。
    """
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleAddRow"))
    helpers.APP.processEvents()

    assert len(_rows(window)) == 2
    assert _plans(window)[1]["steps"] == []


def test_delete_row_button_removes_that_plan():
    """测什么：点某一行的 ✕ → 只少那一行。

    走过的界面：伤害计算窗口 →「＋ 新的计算」→ 最后一行行尾的 ✕。
    """
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleAddRow"))
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_all(window, "battleRowDelete")[-1])
    helpers.APP.processEvents()

    assert len(_rows(window)) == 1


def test_clear_button_empties_every_row():
    """测什么：点「清空」→ 一行都不剩（回到空态提示）。

    走过的界面：伤害计算窗口 →「＋ 新的计算」→「清空」。
    """
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleAddRow"))
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "battleClear"))
    helpers.APP.processEvents()

    assert _rows(window) == []


def test_pick_monster_from_menu_then_run_computes():
    """测什么：从问号菜单里选一只怪 → 这一步进计划；点「计算」→ 掉血 540、剩 460。

    走过的界面：伤害计算窗口 → 行尾问号 → 菜单里「血蚊」→「计算」→ 行上的结果。
    """
    controller, engine, window = _open()
    _add_step(window, "血蚊")
    assert [s["name"] for s in _steps(window)] == ["血蚊"]

    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    results = window.property("battlePlanResults")
    results = results.toVariant() if hasattr(results, "toVariant") else results
    assert results[0]["total_damage"] == 540
    assert results[0]["hp_after"] == 460


def test_item_tab_adds_resource_step():
    """测什么：菜单切到「资源」页 → 选红宝石 → 这一步是资源（不是怪）。

    走过的界面：伤害计算窗口 → 行尾问号 → 菜单顶部「资源」页 → 点「红宝石」。
    """
    controller, engine, window = _open()
    assert _open_menu(window)
    helpers.click_item(window, helpers.find_item(window, "battleTabItem"))
    assert str(window.property("battlePickTab")) == "item"

    helpers.click_item(window, _pick_row(window, "红宝石"))

    steps = _steps(window)
    assert [s["kind"] for s in steps] == ["item"]
    assert steps[0]["name"] == "红宝石"


def test_hero_field_edit_updates_hero():
    """测什么：在勇者那一栏把血改成 1500 → 计划里的 hero.hp 变 1500。

    走过的界面：伤害计算窗口 → 勇者那一栏（血量输入框）。
    """
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
    """测什么：点窗口的关闭 → 伤害计算那扇窗没了。

    走过的界面：伤害计算窗口右上角关闭按钮。
    """
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleClose"))
    helpers.APP.processEvents()

    value = window.property("battleWindow")
    value = value.toQObject() if hasattr(value, "toQObject") else value
    assert value is None


# ---- 读取人物 / 粘贴路线 / 往中间插一步 / 每格掉血的显示 ----

def test_read_button_reads_person(monkeypatch):
    """测什么：点「读取」→ 真的抓一帧读人物面板，数值回到状态行/勇者那一栏。

    走过的界面：伤害计算窗口「读取」→（桩）抓图 + 读人物 → 状态行。
    """
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
    helpers.wait_for(
        lambda: str(controller.statusData.get("hp") or "") == "842", timeout=2.0)

    assert str(controller.statusData["hp"]) == "842"
    assert str(controller.statusData["atk"]) == "13"


def test_paste_button_adds_plan_from_clipboard(monkeypatch):
    """测什么：剪贴板里有一条路线 JSON → 点「粘贴」→ **再开一行**并带上那一步。

    走过的界面：伤害计算窗口「粘贴」→ 计划区（原来那行还是空的，新的那行有内容）。
    """
    import json
    board = helpers.fake_clipboard(monkeypatch)   # 别动用户真剪贴板
    controller, engine, window = _open()
    board.setText(json.dumps({"steps": [
        {"kind": "monster", "name": "血蚊", "hp": 1200, "atk": 60, "def": 20,
         "icon": "", "count": 1, "skills": []}]}))

    helpers.click_item(window, helpers.find_item(window, "battlePaste"))
    helpers.APP.processEvents()

    plans = _plans(window)
    # 窗口本来就带着一行空的；粘贴是**再开一行**（用户："路线要能复制，可以粘贴到伤害计算界面"）
    assert plans[0]["steps"] == []
    assert [step["name"] for step in plans[1]["steps"]] == ["血蚊"]


def test_arrow_inserts_step_before_that_one():
    """测什么：点第 2 步前面那个箭头选一只怪 → 插在第 2 步**前面**（顺序变 血蚊/血蚊/铁卫）。

    走过的界面：伤害计算窗口 → 行尾问号加两步 → 第 2 步前面的箭头 → 菜单选「血蚊」。
    """
    controller, engine, window = _open()
    controller._monsters.append({"name": "铁卫", "hp": "900", "atk": "50",
                                 "def": "30"})
    controller.monstersChanged.emit()
    helpers.APP.processEvents()
    _add_step(window, "血蚊")
    _add_step(window, "铁卫")
    assert [s["name"] for s in _steps(window)] == ["血蚊", "铁卫"]

    arrows = helpers.find_all(window, "battleRowArrow")
    helpers.click_item(window, arrows[1])
    helpers.click_item(window, _pick_row(window, "血蚊"))

    assert [s["name"] for s in _steps(window)] == \
        ["血蚊", "血蚊", "铁卫"]


def test_damage_label_shows_after_compute():
    """测什么：算完在行上写出掉血数字（540）。

    走过的界面：伤害计算窗口 → 加一步 →「计算」→ 行上的掉血文字。
    """
    controller, engine, window = _open()
    _add_step(window, "血蚊")
    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    text = helpers.find_item(window, "battleRowDamage").property("text")
    assert "540" in str(text)                  # 每回合 70 → 18 回合 → 540


# ---- 两处"状态的显示"：空列表提示、没算进去的技能 ----

def test_empty_hint_shows_after_clearing_plans():
    """测什么：清空之后计划区显示"点＋新的计算"的空态提示。

    走过的界面：伤害计算窗口 →「清空」→ 计划区的空态提示。
    """
    controller, engine, window = _open()
    helpers.click_item(window, helpers.find_item(window, "battleClear"))
    helpers.APP.processEvents()

    empty = helpers.find_item(window, "battleEmpty")
    assert empty is not None and empty.isVisible()
    assert "新的计算" in str(empty.property("text"))


def test_unhandled_skills_are_listed_after_compute():
    """测什么：表里没有的技能名要明说"没算进去"（不能装作算过了）。

    走过的界面：伤害计算窗口 → 加一步（那只怪带一个不认识的技能）→「计算」→ 提示那一行。
    """
    controller, engine, window = _open()
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "神秘技能", "code": "", "params": {}}]}]
    controller.monstersChanged.emit()
    helpers.APP.processEvents()
    _add_step(window, "血蚊")
    helpers.click_item(window, helpers.find_item(window, "battlePlanRun"))
    helpers.APP.processEvents()

    note = helpers.find_item(window, "battleUnhandled")
    assert note is not None and note.isVisible()
    assert "没算进去" in str(note.property("text"))


# ---- 两个页签 + 行尾那个箭头 ----

def test_pick_tab_switches_back_to_monsters():
    """测什么：菜单先切到「资源」再切回「怪物」→ 列表里又只有怪。

    走过的界面：伤害计算窗口 → 行尾问号 → 菜单「资源」→ 菜单「怪物」。
    """
    controller, engine, window = _open()
    assert _open_menu(window)
    helpers.click_item(window, helpers.find_item(window, "battleTabItem"))
    assert str(window.property("battlePickTab")) == "item"

    helpers.click_item(window, helpers.find_item(window, "battleTabMonster"))
    assert str(window.property("battlePickTab")) == "monster"
    rows = helpers.find_all(window, "battlePickRow")
    assert rows
    assert any("血蚊" in text for row in rows
               for text in helpers.texts_of(row))


def test_row_end_arrow_opens_the_menu():
    """测什么：行尾那个箭头点开菜单，并且知道是给第几行加（battleMenuPlan）。

    走过的界面：伤害计算窗口 → 行尾箭头（`battleRowArrowEnd`）。
    """
    controller, engine, window = _open()
    assert str(window.property("battleMenu")) == ""

    helpers.click_item(window, helpers.find_item(window, "battleRowArrowEnd"))

    assert str(window.property("battleMenu")) != ""
    assert int(window.property("battleMenuPlan")) == 0
