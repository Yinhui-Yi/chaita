"""伤害计算里「点某一格改参数」的那张卡片（真点击/真打字）。

以前只测到 `battleSetStep` 这类 Slot，**卡片到 Slot 的接线没人跑过**：点图标打开的是
不是那一格、改数量写回的是不是那一行、点「删除」删的是不是那一格。

真值手写：血蚊 1200/60/20，把数量改成 2 → 那一格的 count 变 2，其余不动。
"""

from ... import helpers


def _menu_ready(window):
    return (str(window.property("battleMenu") or "") != ""
            and helpers.find_all(window, "battlePickRow") != [])


def _click_until(window, name, predicate, tries=5):
    """点一个控件，直到 `predicate` 成立（窗口刚出来时第一下可能没命中）。"""
    for _ in range(tries):
        if predicate():
            return True
        item = helpers.find_item(window, name)
        if item is None:
            helpers.wait_for(lambda: helpers.find_item(window, name) is not None,
                             timeout=0.4)
            continue
        helpers.click_item(window, item)
        helpers.wait_for(predicate, timeout=0.4)
    return bool(predicate())


def _pick_row(window, name, tries=12):
    """下拉里那一行；**等它画出来**（菜单刚打开时列表还是空的）。"""
    for _ in range(tries):
        for row in helpers.find_all(window, "battlePickRow"):
            if any(name in text for text in helpers.texts_of(row)):
                return row
        helpers.wait_for(lambda: helpers.find_all(window, "battlePickRow") != [],
                         timeout=0.4)
    raise AssertionError("下拉里没有「%s」" % name)


def _plan_with_step():
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]
    window.openBattle()
    helpers.APP.processEvents()

    assert _click_until(window, "battleRowAsk",
                        lambda: _menu_ready(window)), "点「＋」没把选择菜单打开"
    for _ in range(5):
        helpers.click_item(window, _pick_row(window, "血蚊"))
        if helpers.wait_for(lambda: _has_step(window), timeout=0.4):
            break
    assert _has_step(window), "选了怪但这一步没进计划"
    return controller, engine, window


def _steps(window, plan=0):
    plans = window.property("battlePlans")
    plans = plans.toVariant() if hasattr(plans, "toVariant") else plans
    return plans[plan]["steps"]


def _has_step(window):
    """这一行已经有步骤了吗（还没建好时形状不完整，当成"没有"）。"""
    try:
        return bool(_steps(window))
    except (IndexError, KeyError, TypeError):
        return False


def _open_card(window):
    assert _click_until(window, "battleRowIcon",
                        lambda: window.property("battleEditLayer") is True), \
        "点那一格的图标没把改参数卡片打开"


def test_edit_card_changes_step_count():
    controller, engine, window = _plan_with_step()
    _open_card(window)

    field = helpers.find_item(window, "battleEditCount")
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", "2")
    helpers.APP.processEvents()

    steps = _steps(window)
    assert steps[0]["count"] == 2
    assert steps[0]["name"] == "血蚊"       # 别的字段不许被顺手改掉


def test_edit_card_changes_step_hp():
    controller, engine, window = _plan_with_step()
    _open_card(window)

    field = helpers.find_item(window, "battleEdithp")
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", "2000")
    helpers.APP.processEvents()

    assert _steps(window)[0]["hp"] == 2000
    assert _steps(window)[0]["atk"] == 60


def test_edit_card_delete_removes_that_step():
    controller, engine, window = _plan_with_step()
    _open_card(window)

    helpers.click_item(window, helpers.find_item(window, "battleEditDelete"))
    helpers.APP.processEvents()

    assert _steps(window) == []
    assert window.property("battleEditLayer") is False


def test_edit_card_done_closes_card():
    controller, engine, window = _plan_with_step()
    _open_card(window)
    before = [dict(step) for step in _steps(window)]

    helpers.click_item(window, helpers.find_item(window, "battleEditDone"))
    helpers.APP.processEvents()

    assert window.property("battleEditLayer") is False
    assert _steps(window) == before
