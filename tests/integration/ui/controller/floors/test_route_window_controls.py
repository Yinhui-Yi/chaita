"""路线链窗口的按钮接线（真点击）：复制 / 删除 / 关闭 / 点格子换内容 / 清空格子。

`test_route_chain.py` 只管"算得对不对"，这一份只管**控件接对没接对**：
「复制」是不是真的写进系统剪贴板、「删」是不是删掉这一条、点格子箭头选的怪
是不是落到**那一格**（不是第一格）、「清空」是不是真的清掉。

路线只有一格（0,0）时，格子下标和显示位置都容易糊在一起，所以用两格来测。
"""

from .... import helpers


def _route(cells=None):
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    # 两格**都有内容**：路线链只画有东西的格（空格不占位置），
    # 一格有东西一格空的话画面上只有一个箭头，测不了"点的是第几格"。
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": [{"name": "血蚊", "count": 1}, {"name": "铁卫", "count": 1}],
        "items": [],
        "grid": {"cells": [{"row": 0, "col": 0, "kind": "monster",
                            "name": "血蚊"},
                           {"row": 0, "col": 1, "kind": "monster",
                            "name": "铁卫"}]}}]
    controller.mapHistoryChanged.emit()
    window.storeRoute("长安1", cells or [{"row": 0, "col": 0},
                                        {"row": 0, "col": 1}])
    helpers.APP.processEvents()
    return controller, engine, window


def _route_window(window):
    value = window.property("routeWindow")
    return value.toQObject() if hasattr(value, "toQObject") else value


def _cells(controller, index=0):
    return controller._map_history[0]["routes"][index]["cells"]


def _pick_row(window, name):
    for row in helpers.find_all(window, "routePickRow"):
        if any(name in text for text in helpers.texts_of(row)):
            return row
    raise AssertionError("路线格子的下拉里没有「%s」：%s"
                         % (name, [helpers.texts_of(r)
                                   for r in helpers.find_all(window,
                                                             "routePickRow")]))


def test_delete_button_removes_route_and_closes():
    controller, engine, window = _route()
    assert len(controller._map_history[0]["routes"]) == 1

    helpers.click_item(window, helpers.find_item(window, "routeDelete"))
    helpers.APP.processEvents()

    assert controller._map_history[0]["routes"] == []
    assert _route_window(window) is None


def test_close_button_closes_window():
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_item(window, "routeClose"))
    helpers.APP.processEvents()

    assert _route_window(window) is None
    # 关窗不删数据
    assert len(controller._map_history[0]["routes"]) == 1


def test_copy_puts_steps_on_the_real_clipboard(monkeypatch):
    helpers.fake_clipboard(monkeypatch)        # 别动用户真剪贴板
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_item(window, "routeCopy"))
    helpers.APP.processEvents()

    import json
    data = json.loads(controller.clipboardText())
    steps = data["steps"]
    # 第一格是血蚊（路线创建时按 grid 填进去的），第二格是铁卫
    assert steps[0]["kind"] == "monster"
    assert steps[0]["name"] == "血蚊"
    assert steps[1]["name"] == "铁卫"


def test_cell_menu_fills_the_tapped_cell():
    """点第 2 格的箭头选铁卫：落在第 2 格，第 1 格不动。"""
    controller, engine, window = _route()
    arrows = helpers.find_all(window, "routeCellArrow")
    helpers.click_item(window, arrows[1])

    helpers.click_item(window, _pick_row(window, "铁卫"))

    cells = _cells(controller)
    assert cells[0]["name"] == "血蚊"       # 第一格没被串改
    assert cells[1]["name"] == "铁卫"
    assert cells[1]["kind"] == "monster"


def test_cell_menu_clear_empties_that_cell():
    """点第 2 格的箭头 → 选「清空」：只清这一格，第 1 格不动。"""
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_all(window, "routeCellArrow")[1])
    helpers.click_item(window, helpers.find_item(window, "routeCellClear"))

    cells = _cells(controller)
    assert not cells[1].get("name")
    assert not cells[1].get("kind")
    assert cells[0]["name"] == "血蚊"


def test_cell_menu_item_tab_lists_resources():
    """格子菜单也有"资源"页：切过去能选宝石（不只怪）。"""
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_all(window, "routeCellArrow")[1])
    helpers.click_item(window, helpers.find_item(window, "routeTabItem"))
    assert str(window.property("routePickTab")) == "item"

    rows = helpers.find_all(window, "routePickRow")
    assert rows, "资源页应该有东西可选"
    helpers.click_item(window, _pick_row(window, "红宝石"))

    cell = _cells(controller)[1]
    assert cell["kind"] == "item"
    assert cell["name"] == "红宝石"


def test_door_button_marks_cell_as_door():
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_all(window, "routeCellArrow")[0])
    helpers.click_item(window, helpers.find_item(window, "routeCellDoor"))

    assert _cells(controller)[0]["kind"] == "door"


# ---- 点格子芯片 → 改参数卡片（改数量/血量、删这步、改完关掉）----

def _open_cell_card(window):
    chips = helpers.find_all(window, "routeCellChip")
    assert chips, "路线链上应该有一格可以点"
    # 用 find_all（按屏幕位置排序）拿**第一格**；find_item 是遍历顺序，可能先拿到第二格
    assert _click_until(window, chips[0], None), "点格子芯片没打开改参数卡片"


def _click_until(window, item, _unused=None, tries=5):
    """点这个控件，直到改参数卡片打开（窗口刚出来时第一下可能没命中）。"""
    for _ in range(tries):
        if window.property("routeEditLayer") is True:
            return True
        helpers.click_item(window, item)
        helpers.wait_for(lambda: window.property("routeEditLayer") is True,
                         timeout=0.4)
    return bool(window.property("routeEditLayer") is True)


def test_cell_card_edit_count_writes_back():
    controller, engine, window = _route()
    _open_cell_card(window)

    field = helpers.find_item(window, "routeEditCount")
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", "3")
    helpers.APP.processEvents()

    cells = _cells(controller)
    assert cells[0].get("count") == 3
    assert cells[0]["name"] == "血蚊"          # 别的字段不许被顺手改掉


def test_cell_card_edit_hp_writes_back():
    controller, engine, window = _route()
    _open_cell_card(window)

    field = helpers.find_item(window, "routeEdithp")
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", "2000")
    helpers.APP.processEvents()

    cells = _cells(controller)
    assert cells[0]["hp"] == 2000
    assert cells[0]["atk"] == 60


def test_cell_card_remove_clears_that_cell():
    controller, engine, window = _route()
    _open_cell_card(window)

    helpers.click_item(window, helpers.find_item(window, "routeEditDelete"))
    helpers.APP.processEvents()

    cells = _cells(controller)
    assert not cells[0].get("name")            # 这一格回到"只是走过"
    assert not cells[0].get("kind")
    assert window.property("routeEditLayer") is False


def test_cell_card_done_closes_without_changing():
    controller, engine, window = _route()
    _open_cell_card(window)
    before = [dict(cell) for cell in _cells(controller)]

    helpers.click_item(window, helpers.find_item(window, "routeEditDone"))
    helpers.APP.processEvents()

    assert window.property("routeEditLayer") is False
    assert _cells(controller) == before


def _sheet_with_route(cells):
    """直接摆一条路线记录并打开链窗口（`saveRoute` 不让存空格子，这里绕过它）。"""
    controller, engine, window = _route()
    controller._map_history[0]["routes"] = [{"at": "10:00", "cells": cells}]
    controller.mapHistoryChanged.emit()
    window.openRoute("长安1", 0)
    helpers.APP.processEvents()
    return controller, engine, window


def test_route_empty_hint_shows_for_empty_route():
    """老数据里可能有一条"没有格子"的路线：链上要出提示，而不是一片空白。"""
    controller, engine, window = _sheet_with_route([])
    helpers.APP.processEvents()

    empty = helpers.find_item(window, "routeEmpty")
    assert empty is not None and empty.isVisible()
    assert helpers.find_all(window, "routeCellChip") == []


# ---- 链上的两处读数：勇者那一行、每格掉血 ----

def test_route_hero_line_shows_hero_stats():
    controller, engine, window = _route()
    line = helpers.find_item(window, "routeHeroLine")

    # 打开路线时把人物数值带出来（血/攻/防/魔防）
    text = str(line.property("text") if line.property("text") is not None
               else "")
    assert "1000" in text or "90" in text


def test_route_cell_damage_shows_after_compute():
    """算完在每格后面写掉血。手算：血蚊 1200 血 / 防 20，勇者攻 90 →
    每回合 70 → 18 回合 → 挨 17 下 ×(60-30)=30 → 510（这套数据没有先攻技能）。"""
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_item(window, "routeRun"))
    helpers.APP.processEvents()

    damages = helpers.find_all(window, "routeCellDamage")
    assert damages, "算完之后每格后面应该有掉血数字"
    assert "510" in str(damages[0].property("text"))
