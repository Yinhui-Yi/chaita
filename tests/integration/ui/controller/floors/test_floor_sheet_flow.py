"""「这一层」小窗的操作链路（真点击 / 真打字，打的是 QML 里的按钮和输入框）。

为什么单独写：以前这些只测到 controller 的 Slot 层，QML 那半截（`openPickMenu`、
`pickRow`、`TextField.onEditingFinished`、两下确认删除）从来没人跑过 ——
本轮就是栽在"测试绕过 QML"上的。

真值全部手写：加一条怪 = 手册里那一条、数量 1；加一条资源 = 带图标 + 道具表默认效果；
点图标换种类 = 名字/图标一起换；备注 = 原样存进那一层；删除本层要点两下。
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from .... import helpers


def _sheet(mons=None, items=None, routes=None, url=""):
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
    window.setProperty("floorWindows", ["长安1"])
    helpers.wait_for(lambda: window.floorSheetOf("长安1") is not None)
    return controller, engine, window


def _entry(controller, index=0):
    return controller._map_history[index]


def _pick_row(window, name):
    """下拉里名字含 `name` 的那一行（真控件）。"""
    for row in helpers.find_all(window, "pickRow"):
        if any(name in text for text in helpers.texts_of(row)):
            return row
    raise AssertionError("下拉里没有「%s」这一条：%s"
                         % (name, [helpers.texts_of(r)
                                   for r in helpers.find_all(window, "pickRow")]))


def _type(window, item, text):
    """真的在这个输入框里打完字再按回车（走 editingFinished）。"""
    item.forceActiveFocus()
    helpers.APP.processEvents()
    item.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(item.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    helpers.APP.processEvents()


def test_add_monster_from_pick_menu():
    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorAddMon"))
    assert str(window.property("pickMode")) == "mon"

    helpers.click_item(window, _pick_row(window, "血蚊"))

    assert _entry(controller)["mons"] == [{"name": "血蚊", "count": 1}]
    assert str(window.property("pickMode")) == ""      # 选完自己收起来


def test_add_item_from_pick_menu_carries_icon_and_effect(monkeypatch):
    from chaita.game import iteminfo
    monkeypatch.setattr(iteminfo, "save_icon_map", lambda *a, **k: None)
    controller, engine, window = _sheet()

    helpers.click_item(window, helpers.find_item(window, "floorAddItem"))
    assert str(window.property("pickMode")) == "item"
    helpers.click_item(window, _pick_row(window, "红宝石"))

    assert _entry(controller)["items"] == [
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1,
         "icon": "gem_red"}]


def test_item_icon_pick_changes_kind(monkeypatch):
    """点资源图标 → 选「铁剑」→ 这一条的名字和图标一起换成剑。"""
    from chaita.game import iteminfo
    monkeypatch.setattr(iteminfo, "save_icon_map", lambda *a, **k: None)
    controller, engine, window = _sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1,
         "icon": "gem_red"}])

    helpers.click_item(window, helpers.find_item(window, "floorItemIconPick"))
    assert int(window.property("pickReplaceIndex")) == 0
    helpers.click_item(window, _pick_row(window, "铁剑"))

    item = _entry(controller)["items"][0]
    assert item["name"] == "铁剑"
    assert item["icon"] == "xinxin2_sword1"


def test_floor_memo_field_saves():
    controller, engine, window = _sheet()
    _type(window, helpers.find_item(window, "floorMemo"), "记得拿宝石")

    assert _entry(controller)["memo"] == "记得拿宝石"


def test_route_memo_field_saves_manual_text():
    controller, engine, window = _sheet(
        routes=[{"at": "10:00", "cells": [{"row": 0, "col": 0}]}])
    _type(window, helpers.find_item(window, "routeMemo"), "手写一句")

    assert _entry(controller)["routes"][0]["memo"] == "手写一句"
    # 计算那半截仍然是实时算出来的（没被写进备注）
    assert window.routeStatsFor("长安1", 0) == "血 1000 · 攻 90 · 防 30 · 魔防 10"


def test_delete_floor_needs_two_clicks():
    controller, engine, window = _sheet()
    button = helpers.find_item(window, "floorDelete")

    helpers.click_item(window, button)
    assert button.property("label") == "再点一次删除"
    assert len(controller._map_history) == 1          # 第一下只是上膛

    helpers.click_item(window, button)
    helpers.APP.processEvents()
    assert controller._map_history == []
    assert window.property("floorWindows").toVariant() == []


def test_done_button_replies_saved_and_closes_sheet():
    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorDone"))
    helpers.APP.processEvents()

    assert controller._chat_reply == "已保存「长安1」"
    assert window.property("floorWindows").toVariant() == []


def test_refresh_without_screenshot_reports_failure():
    """没有地图截图时点「刷新本层」：不能静默 return，要出一条失败任务。"""
    controller, engine, window = _sheet(url="")
    helpers.click_item(window, helpers.find_item(window, "floorRefresh"))
    helpers.APP.processEvents()

    task = controller._tasks[0]
    assert task["state"] == "failed"
    assert "还没有地图截图" in task["text"]


def test_clicking_outside_closes_the_pick_menu():
    """下拉菜单点外面就收起（不然它会一直挂在那儿挡住地图）。"""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorAddMon"))
    assert str(window.property("pickMode")) == "mon"

    sheet = window.floorSheetOf("长安1")
    layer = helpers.find_item(window, "pickLayer")
    # 左下角：菜单卡片挂在按钮下面，这一角一定是"外面"
    point = layer.mapToScene(QPointF(4, layer.height() - 4))
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        helpers.APP.sendEvent(sheet, QMouseEvent(kind, point, point,
                                                 Qt.LeftButton, Qt.LeftButton,
                                                 Qt.NoModifier))
    helpers.APP.processEvents()

    assert str(window.property("pickMode")) == ""
