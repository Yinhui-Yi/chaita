"""「这一层」小窗的操作链路（**集成测试**，真点击 / 真打字）。

为什么单独写：以前这些只测到 controller 的 Slot 层，QML 那半截（`openPickMenu`、
`pickRow`、`TextField.onEditingFinished`、两下确认删除）从来没人跑过 —— 曾经就是
栽在"测试绕过 QML"上的。

真值全部手写：加一条怪 = 手册里那一条、数量 1；加一条资源 = 带图标 + 道具表默认效果；
点图标换种类 = 名字/图标一起换；备注 = 原样存进那一层；删除本层要点两下。

标准见 `tests/integration/README.md`。驱动：点「清单 ›」开窗 → 点窗里的按钮/输入框。
断言读公开属性（`controller.mapHistory / chatReply / tasks`、`window.pickMode /
pickReplaceIndex / floorWindows`）。起点数据直接摆。
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from .... import helpers


def _sheet(mons=None, items=None, routes=None, url=""):
    """摆好这一层的数据，再点「清单 ›」把那扇小窗打开。"""
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    # 怪物行/加怪下拉读的是缓存属性：不发信号，界面还拿着上一轮测试的名单
    controller.monstersChanged.emit()
    controller._map_history = [{
        "floor": "长安1", "url": url,
        "mons": mons or [], "items": items or [],
        "grid": {"cells": []}, "routes": routes or []}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    assert helpers.wait_for(
        lambda: helpers.find_item(window, "mapSheet") is not None), \
        "地图那一栏没出来"
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("长安1") is not None), "清单没打开"
    helpers.APP.processEvents()
    return controller, engine, window


def _entry(controller, index=0):
    """这一层的记录（公开属性 `mapHistory`）。"""
    value = controller.mapHistory
    rows = value.toVariant() if hasattr(value, "toVariant") else value
    return rows[index]


def _pick_row(window, name):
    """下拉里名字含 `name` 的那一行（真控件）。

    下拉只有一小截高（按小窗的空间收着），要点的行不一定在可见区里：
    先像用户那样把它滚进来看得见的地方，再点。
    """
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent
    target = None
    for row in helpers.find_all(window, "pickRow"):
        if any(name in text for text in helpers.texts_of(row)):
            target = row
            break
    if target is None:
        raise AssertionError("下拉里没有「%s」这一条：%s"
                             % (name, [helpers.texts_of(r)
                                       for r in helpers.find_all(window,
                                                                 "pickRow")]))
    flick = helpers.find_item(window, "pickFlick")
    if flick is not None:
        top = float(target.y())
        view = float(flick.height())
        if top < 0 or top + target.height() > view:
            flick.setProperty("contentY", max(0.0, top - view / 2))
            helpers.APP.processEvents()
    return target


def _type(window, item, text):
    """真的在这个输入框里打完字再按回车（走 editingFinished）。"""
    helpers.focus_field(item)
    item.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(item.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def test_add_monster_from_pick_menu():
    """测什么：加怪下拉里选一只 → 这一层多一条怪（数量 1），下拉自己收起。

    交互顺序：① 点「清单 ›」开这一层 ② 点「＋ 加怪」 ③ 点下拉里的「血蚊」
    → 断言 `mapHistory[0].mons == [{血蚊, 1}]`、`pickMode` 变空。
    """
    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorAddMon"))
    assert str(window.property("pickMode")) == "mon"

    helpers.click_item(window, _pick_row(window, "血蚊"))

    assert _entry(controller)["mons"] == [{"name": "血蚊", "count": 1,
                                           "manual": True}]
    assert str(window.property("pickMode")) == ""      # 选完自己收起来


def test_add_item_from_pick_menu_carries_icon_and_effect(monkeypatch):
    """测什么：加资源下拉里选红宝石 → 带图标和道具表默认效果、数量 1。

    交互顺序：① 开「清单 ›」 ② 点「＋ 加资源」 ③ 点下拉里的「红宝石」
    → 断言 `items[0]` 的 name/effect/icon/count。
    """
    from chaita.game import iteminfo
    monkeypatch.setattr(iteminfo, "save_icon_map", lambda *a, **k: None)
    controller, engine, window = _sheet()

    helpers.show_section(window, "item")
    helpers.click_item(window, helpers.find_item(window, "floorAddItem"))
    assert str(window.property("pickMode")) == "item"
    helpers.click_item(window, _pick_row(window, "红宝石"))

    assert _entry(controller)["items"] == [
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1,
         "icon": "gem_red", "manual": True}]


def test_item_icon_pick_changes_kind(monkeypatch):
    """测什么：点资源行的图标换成剑 → 名字和图标一起换。

    交互顺序：① 开「清单 ›」（这一层已经有一条红宝石）② 点那一行的图标
    ③ 下拉里点「铁剑」→ 断言这条的名字变铁剑、icon 变 sword。
    """
    from chaita.game import iteminfo
    monkeypatch.setattr(iteminfo, "save_icon_map", lambda *a, **k: None)
    controller, engine, window = _sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1,
         "icon": "gem_red"}])

    helpers.show_section(window, "item")
    helpers.click_item(window, helpers.find_item(window, "floorItemIconPick"))
    assert int(window.property("pickReplaceIndex")) == 0
    helpers.click_item(window, _pick_row(window, "铁剑"))

    item = _entry(controller)["items"][0]
    assert item["name"] == "铁剑"
    assert item["icon"] == "sword"


def test_floor_memo_field_saves():
    """测什么：这一层的备注写完回车就存进那一层。

    交互顺序：① 开「清单 ›」 ② 备注框打字回车 → 断言 `mapHistory[0].memo`。
    """
    controller, engine, window = _sheet()
    _type(window, helpers.find_item(window, "floorMemo"), "记得拿宝石")

    assert _entry(controller)["memo"] == "记得拿宝石"


def test_delete_floor_needs_two_clicks():
    """测什么：删这一层要点两下（第一下只上膛，第二下才删）；菜单一关就解除上膛。

    交互顺序：① 开「清单 ›」 ② 点标题行「⋯」→「删除本层」（文字变「再点一次：确认删除」）
    ③ 再点一次 → 断言层没了、小窗关了。
    """
    controller, engine, window = _sheet()
    helpers.open_sheet_menu(window)
    button = helpers.find_item(window, "floorDelete")

    helpers.click_item(window, button)
    assert button.property("label") == "再点一次：确认删除"
    assert len(controller.mapHistory) == 1, "第一下只是上膛，不能删"

    helpers.click_item(window, button)
    helpers.APP.processEvents()
    assert list(controller.mapHistory) == []
    assert window.property("floorWindows").toVariant() == []


def test_closing_the_menu_disarms_the_delete():
    """测什么：点了一下「删除本层」又按 Esc 关菜单 → 再打开还是「删除本层」，没删。

    不解除的话，隔一会儿再开菜单一点就删掉整层了。
    """
    controller, engine, window = _sheet()
    helpers.open_sheet_menu(window)
    helpers.click_item(window, helpers.find_item(window, "floorDelete"))
    sheet = window.floorSheetOf("长安1")
    helpers.APP.sendEvent(sheet, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape,
                                           Qt.NoModifier))
    helpers.APP.processEvents()

    helpers.open_sheet_menu(window)

    assert helpers.find_item(window, "floorDelete").property("label") == "删除本层"
    assert len(controller.mapHistory) == 1


def test_sheet_has_no_done_button():
    """测什么：不再有「完成」按钮 —— 改动是即时存的，关窗（✕）就是收工。"""
    controller, engine, window = _sheet()

    assert helpers.find_item(window, "floorDone") is None
    helpers.click_item(window, helpers.find_item(window, "floorClose"))
    helpers.APP.processEvents()
    assert window.property("floorWindows").toVariant() == []


def test_refresh_without_screenshot_reports_failure():
    """测什么：没有地图截图时点「刷新本层」不能静默 return，要出一条失败任务。

    交互顺序：① 开「清单 ›」（这一层 url 为空）② 点「⋯」→「刷新本层」
    → 断言 `controller.tasks[0]` 是 failed 且文案说明没有截图。
    """
    controller, engine, window = _sheet(url="")
    helpers.open_sheet_menu(window)
    helpers.click_item(window, helpers.find_item(window, "floorRefresh"))
    helpers.APP.processEvents()

    task = controller.tasks[0]
    assert task["state"] == "failed"
    assert "还没有地图截图" in task["text"]


def test_clicking_outside_closes_the_pick_menu():
    """测什么：加怪下拉点外面就收起（不然一直挂着挡住地图）。

    交互顺序：① 开「清单 ›」 ② 点「＋ 加怪」 ③ 在下拉外面（窗口左下角）点一下
    → 断言 `pickMode` 变空。
    """
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorAddMon"))
    assert str(window.property("pickMode")) == "mon"

    sheet = window.floorSheetOf("长安1")
    layer = helpers.find_item(window, "pickLayer")
    point = layer.mapToScene(QPointF(4, layer.height() - 4))
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        helpers.APP.sendEvent(sheet, QMouseEvent(kind, point, point,
                                                 Qt.LeftButton, Qt.LeftButton,
                                                 Qt.NoModifier))
    helpers.APP.processEvents()

    assert str(window.property("pickMode")) == ""
