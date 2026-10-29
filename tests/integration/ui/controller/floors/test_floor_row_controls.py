"""「这一层」词条行上的小控件（真点击 / 真打字）：数量、勾掉、删掉。

以前这些只在 controller 的 Slot 层测过，QML 那半截（`saveFloorMonsterField` 传哪
个 index、勾用的是 `_src` 还是显示顺序、✕ 到底删的是哪一行）没人跑过。
删除/勾掉都按**真实列表下标**走，显示顺序和存储顺序不一致时最容易错行。
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from .... import helpers


def _sheet(mons=None, items=None):
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    # 行/下拉读的是缓存属性，不发信号界面还拿着上一轮的名单
    controller.monstersChanged.emit()
    controller._map_history = [{
        "floor": "长安1", "url": "",
        "mons": mons or [], "items": items or [],
        "grid": {"cells": []}, "routes": []}]
    window.setProperty("floorWindows", ["长安1"])
    helpers.wait_for(lambda: window.floorSheetOf("长安1") is not None)
    return controller, engine, window


def _entry(controller):
    return controller._map_history[0]


def _type(window, item, text):
    item.forceActiveFocus()
    helpers.APP.processEvents()
    item.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(item.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def test_monster_count_field_saves():
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    _type(window, helpers.find_item(window, "floorMonCount"), "5")
    assert _entry(controller)["mons"][0]["count"] == 5


def test_monster_done_tick_toggles():
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    helpers.click_item(window, helpers.find_item(window, "floorMonDone"))
    assert _entry(controller)["mons"][0]["done"] is True

    helpers.click_item(window, helpers.find_item(window, "floorMonDone"))
    assert not _entry(controller)["mons"][0].get("done")


def test_monster_delete_removes_that_row():
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1},
                                              {"name": "铁卫", "count": 1}])
    rows = helpers.find_all(window, "floorMonDelete")
    helpers.click_item(window, rows[1])

    assert [m["name"] for m in _entry(controller)["mons"]] == ["血蚊"]


def test_item_done_tick_toggles():
    controller, engine, window = _sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1, "icon": "gem_red"}])
    helpers.click_item(window, helpers.find_item(window, "floorItemDone"))
    assert _entry(controller)["items"][0]["done"] is True

    helpers.click_item(window, helpers.find_item(window, "floorItemDone"))
    assert not _entry(controller)["items"][0].get("done")


def test_item_delete_removes_that_row():
    controller, engine, window = _sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1, "icon": "gem_red"},
        {"name": "红钥匙", "effect": "", "count": 1, "icon": "h5_redKey"}])
    # 显示顺序是"宝石 → 钥匙"，存储顺序也是；删第二行 = 钥匙
    rows = helpers.find_all(window, "floorItemDelete")
    helpers.click_item(window, rows[1])

    assert [i["name"] for i in _entry(controller)["items"]] == ["红宝石"]


# ---- 数量那个上下箭头（NumberStepper）----

def test_item_count_arrow_increments_and_commits():
    """点一下上箭头 +1，**松手才落库**（按住连加时中间不写盘）。"""
    controller, engine, window = _sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 3, "icon": "gem_red"}])

    helpers.click_item(window, helpers.find_item(window, "floorItemCountUp"))
    helpers.APP.processEvents()
    assert _entry(controller)["items"][0]["count"] == 4

    helpers.click_item(window, helpers.find_item(window, "floorItemCountDown"))
    helpers.APP.processEvents()
    assert _entry(controller)["items"][0]["count"] == 3

    # 再点一下下箭头 → 2；不会掉到负数
    helpers.click_item(window, helpers.find_item(window, "floorItemCountDown"))
    helpers.APP.processEvents()
    assert _entry(controller)["items"][0]["count"] == 2
