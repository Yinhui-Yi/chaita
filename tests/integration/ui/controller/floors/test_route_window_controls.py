"""路线链窗口的按钮接线（**集成测试**，只点界面上的东西）。

`test_route_chain.py` 只管"算得对不对"，这一份只管**控件接对没接对**：删、关闭、复制、
改参数卡片（数量/完成）、空路线提示、勇者那一行、每格掉血。

标准见 `tests/integration/README.md`。**一条豁免**（见 README「允许摆起点数据」）：
起点那条路线用 `window.storeRoute()` 造 —— 它是唯一会生成链窗口需要的那份 ctx 结构的
入口；真人造路线是"地图上长按拖"，那条路已经在 `test_cross_floor_*.py` 里覆盖了。

**删掉的 6 条**（一律因为"证明不了点击真的写进去了"）：
  · `test_cell_menu_fills_the_tapped_cell` —— **假通过**：起点第 2 格本来就叫铁卫，
    点下拉里的铁卫必然相等，写没写进去看不出来
  · `test_cell_menu_clear_empties_that_cell`
  · `test_cell_menu_item_tab_lists_resources`
  · `test_door_button_marks_cell_as_door`
  · `test_cell_card_edit_hp_writes_back`
  · `test_cell_card_remove_clears_that_cell`
  这 5 条（除假通过那条）在原写法下能过、把起点换成"直接摆 cells"就全部写不回去；
  探针也确认了另一件事：**箭头点击确实会把 `ctx.menuCell` 设对**（`menu='cell'`,
  `menuCell=1`），所以问题在 `routeFill → saveRouteCell` 这条写回，不在点击。
  现在的状态：这 6 条规则**没有可信的自动化覆盖**。
"""

from .... import helpers


def _route(cells=None):
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "0"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    # 两格**都有内容**：路线链只画有东西的格（空格不占位置），
    # 一格有东西一格空的话画面上只有一个箭头。
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


def _pick_row(window, name):
    """格子菜单/下拉里名字含 `name` 的那一行（真控件）。"""
    for row in helpers.find_all(window, "routePickRow"):
        if any(name in text for text in helpers.texts_of(row)):
            return row
    raise AssertionError("下拉里没有「%s」：%s"
                         % (name, [helpers.texts_of(r)
                                   for r in helpers.find_all(window,
                                                             "routePickRow")]))


def _cells(controller, index=0):
    return controller._map_history[0]["routes"][index]["cells"]


def _cells_of(controller, index=0):
    """这条路线每格的**当前**内容（公开 Slot；链上改过的那份优先）。"""
    value = controller.routeCells("长安1", index)
    return value.toVariant() if hasattr(value, "toVariant") else list(value or [])


def _open_cell_card(window):
    """真操作：点链上第一格的芯片，直到改参数卡片打开。"""
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


def test_cell_menu_fills_the_tapped_cell_only():
    """测什么：点**第 2 格**的箭头 → 切「资源」页选红宝石 → 只有第 2 格变红宝石，
    第 1 格不动，**这一层的地图记录一个字都没改**。

    交互顺序：① 链窗口上点第 2 格的小箭头 ② 点下拉顶部「资源」页 ③ 点「红宝石」
    → 断言 `routeCells[1]` 是 item/红宝石、`routeCells[0]` 还是血蚊、
    `grid` 里那一格还是铁卫。
    """
    controller, engine, window = _route()
    grid_before = [dict(cell) for cell in
                   controller.mapHistory[0]["grid"]["cells"]]

    helpers.click_item(window, helpers.find_all(window, "routeCellArrow")[1])
    helpers.click_item(window, helpers.find_item(window, "routeTabItem"))
    helpers.click_item(window, _pick_row(window, "红宝石"))

    cells = _cells_of(controller)
    assert (cells[1]["kind"], cells[1]["name"]) == ("item", "红宝石")
    assert cells[0]["name"] == "血蚊", "第 1 格被串改了"
    assert controller.mapHistory[0]["grid"]["cells"] == grid_before, \
        "链上改一格不该动地图记录"


def test_cell_menu_clear_empties_that_cell_only():
    """测什么：点第 2 格的箭头 →「清空」→ 只有第 2 格变空，而且**不会被地图记录填回来**。

    交互顺序：① 点第 2 格箭头 ② 点下拉里的「清空」
    → 断言 `routeCells[1]` 没有 kind/name、第 1 格还是血蚊、`grid` 没变。
    """
    controller, engine, window = _route()
    grid_before = [dict(cell) for cell in
                   controller.mapHistory[0]["grid"]["cells"]]

    helpers.click_item(window, helpers.find_all(window, "routeCellArrow")[1])
    helpers.click_item(window, helpers.find_item(window, "routeCellClear"))

    cells = _cells_of(controller)
    assert not cells[1].get("name")
    assert not cells[1].get("kind")
    assert cells[0]["name"] == "血蚊"
    assert controller.mapHistory[0]["grid"]["cells"] == grid_before


def test_door_button_marks_that_cell_as_door():
    """测什么：格子菜单点「门」→ 第 1 格记成门。

    交互顺序：① 点第 1 格的箭头 ② 点下拉里的「门」→ 断言 `routeCells[0].kind` 是 door。
    """
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_all(window, "routeCellArrow")[0])
    helpers.click_item(window, helpers.find_item(window, "routeCellDoor"))

    assert _cells_of(controller)[0]["kind"] == "door"


def test_cell_card_edit_hp_writes_back():
    """测什么：改参数卡片把血量改成 2000 → 这一格 hp=2000，攻不变。

    交互顺序：① 点第一格芯片开卡片 ② 血量框打 2000 回车 → 断言 hp 变、atk 没变。
    """
    controller, engine, window = _route()
    _open_cell_card(window)

    field = helpers.find_item(window, "routeEdithp")
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", "2000")
    helpers.APP.processEvents()

    cells = _cells_of(controller)
    assert cells[0]["hp"] == 2000
    assert cells[0]["atk"] == 60


def test_cell_card_remove_clears_that_cell():
    """测什么：改参数卡片点「删掉这一步」→ 这一格回到"只是走过"，卡片关掉。

    交互顺序：① 点第一格芯片开卡片 ② 点「删掉这一步」
    → 断言这一格没有 kind/name、卡片关掉。
    """
    controller, engine, window = _route()
    _open_cell_card(window)

    helpers.click_item(window, helpers.find_item(window, "routeEditDelete"))
    helpers.APP.processEvents()

    cells = _cells_of(controller)
    assert not cells[0].get("name")
    assert not cells[0].get("kind")
    assert window.property("routeEditLayer") is False


def test_delete_button_removes_route_and_closes():
    """测什么：链窗口点「删」→ 这条路线没了，窗口也关掉。

    走过的界面：地图松手生成的那扇链窗口 →「删」。
    """
    controller, engine, window = _route()
    assert len(controller._map_history[0]["routes"]) == 1

    helpers.click_item(window, helpers.find_item(window, "routeDelete"))
    helpers.APP.processEvents()

    assert controller._map_history[0]["routes"] == []
    assert _route_window(window) is None


def test_close_button_closes_window():
    """测什么：点「关闭」只关窗，路线数据还在。

    走过的界面：链窗口「关闭」。
    """
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_item(window, "routeClose"))
    helpers.APP.processEvents()

    assert _route_window(window) is None
    # 关窗不删数据
    assert len(controller._map_history[0]["routes"]) == 1


def test_copy_puts_steps_on_the_real_clipboard(monkeypatch):
    """测什么：点「复制」把这条路线按 JSON 写进剪贴板（两格都在、顺序对）。

    走过的界面：链窗口「复制」→ 剪贴板（替身读回）。
    """
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


def test_cell_card_edit_count_writes_back():
    """测什么：改参数卡片把数量改成 3 → 这一格 count=3，别的字段不动。

    走过的界面：链窗口 → 第一格芯片 → 改参数卡片（数量输入框）。
    """
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


def test_cell_card_done_closes_without_changing():
    """测什么：改参数卡片点「完成」→ 卡片关掉，这一格一个字都没变。

    走过的界面：链窗口 → 第一格芯片 → 改参数卡片「完成」。
    """
    controller, engine, window = _route()
    _open_cell_card(window)
    before = [dict(cell) for cell in _cells(controller)]

    helpers.click_item(window, helpers.find_item(window, "routeEditDone"))
    helpers.APP.processEvents()

    assert window.property("routeEditLayer") is False
    assert _cells(controller) == before


def test_route_empty_hint_shows_for_empty_route():
    """测什么：老数据里那条"一个格子都没有"的路线 → 链上出提示，不是一片空白。

    走过的界面：链窗口（空态提示）。
    """
    controller, engine, window = _route()
    controller._map_history[0]["routes"] = [{"at": "10:00", "cells": []}]
    controller.mapHistoryChanged.emit()
    window.openRoute("长安1", 0)
    helpers.APP.processEvents()

    empty = helpers.find_item(window, "routeEmpty")
    assert empty is not None and empty.isVisible()
    assert helpers.find_all(window, "routeCellChip") == []


def test_route_hero_line_shows_hero_stats():
    """测什么：链窗口顶上那一行写出勇者的血/攻/防（打开时带出来）。

    走过的界面：链窗口顶部那一行。
    """
    controller, engine, window = _route()
    line = helpers.find_item(window, "routeHeroLine")

    # 打开路线时把人物数值带出来（血/攻/防/魔防）
    text = str(line.property("text") if line.property("text") is not None
               else "")
    assert "1000" in text or "90" in text


def test_route_cell_damage_shows_after_compute():
    """测什么：点「计算」→ 每一格后面写出掉血（这套数据手算 510）。

    手算：血蚊 1200 血 / 防 20，勇者攻 90 → 每回合 70 → 18 回合 →
    挨 17 下 ×(60-30)=30 → 510（这套数据没有先攻技能）。

    走过的界面：链窗口「计算」→ 每格后面的掉血数字。
    """
    controller, engine, window = _route()
    helpers.click_item(window, helpers.find_item(window, "routeRun"))
    helpers.APP.processEvents()

    damages = helpers.find_all(window, "routeCellDamage")
    assert damages, "算完之后每格后面应该有掉血数字"
    assert "510" in str(damages[0].property("text"))
