"""「这一层」词条行上的小控件（**集成测试**，真点击 / 真打字）。

覆盖：怪物行/资源行的**数量**、**勾掉打过**、行尾 **✕ 删掉**，以及资源行数量的
上/下箭头（松手才落库）。以前这些只在 controller 的 Slot 层测过，QML 那半截
（`saveFloorMonsterField` 传的是哪个 index、勾用的是 `_src` 还是显示顺序、✕ 删的
是哪一行）没人跑过。删除/勾掉都按**真实列表下标**走，显示顺序和存储顺序不一致时
最容易错行 —— 所以资源那两条特意摆"宝石 → 钥匙"两行，删第 2 行。

标准见 `tests/integration/README.md`。驱动：点「清单 ›」开这一层的小窗 → 点行里的
控件 / 在数量格里打字回车。断言读公开属性（`window.sheetMons/sheetItems(floor)`）。
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from .... import helpers


def _open_sheet(mons=None, items=None):
    """摆好这一层的数据，然后点「清单 ›」把那扇小窗打开。"""
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


def _mons(window):
    value = window.sheetMons("长安1")
    return value.toVariant() if hasattr(value, "toVariant") else list(value or [])


def _items(window):
    value = window.sheetItems("长安1")
    return value.toVariant() if hasattr(value, "toVariant") else list(value or [])


def _type(window, item, text):
    """在某个输入框里打字回车（真实键盘事件收尾）。"""
    item.forceActiveFocus()
    helpers.APP.processEvents()
    item.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(item.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def test_monster_count_field_saves():
    """测什么：在怪物行的数量格里打 5 回车 → 这一只的数量变成 5。

    走过的界面：「清单 ›」小窗 → 怪物行（数量输入框）。
    """
    controller, engine, window = _open_sheet(mons=[{"name": "血蚊", "count": 1}])
    _type(window, helpers.find_item(window, "floorMonCount"), "5")
    assert _mons(window)[0]["count"] == 5


def test_monster_done_tick_toggles():
    """测什么：点行首那个 ○ → 变"打过了"；再点一下撤销。

    走过的界面：「清单 ›」小窗 → 怪物行行首的圆圈（点两次）。
    """
    controller, engine, window = _open_sheet(mons=[{"name": "血蚊", "count": 1}])
    helpers.click_item(window, helpers.find_item(window, "floorMonDone"))
    assert _mons(window)[0]["done"] is True

    helpers.click_item(window, helpers.find_item(window, "floorMonDone"))
    assert not _mons(window)[0].get("done")


def test_monster_delete_removes_that_row():
    """测什么：点第 2 只怪的 ✕ → 只删第 2 行，第 1 行还在（按下标删，不按名字）。

    走过的界面：「清单 ›」小窗 → 第 2 行行尾的 ✕。
    """
    controller, engine, window = _open_sheet(mons=[{"name": "血蚊", "count": 1},
                                                   {"name": "铁卫", "count": 1}])
    rows = helpers.find_all(window, "floorMonDelete")
    helpers.click_item(window, rows[1])

    assert [m["name"] for m in _mons(window)] == ["血蚊"]


def test_item_done_tick_toggles():
    """测什么：资源行行首的 ○ 点一下 = 拿过了，再点撤销。

    走过的界面：「清单 ›」小窗 → 资源行行首的圆圈（点两次）。
    """
    controller, engine, window = _open_sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1, "icon": "gem_red"}])
    helpers.click_item(window, helpers.find_item(window, "floorItemDone"))
    assert _items(window)[0]["done"] is True

    helpers.click_item(window, helpers.find_item(window, "floorItemDone"))
    assert not _items(window)[0].get("done")


def test_item_delete_removes_that_row():
    """测什么：点第 2 个资源的 ✕ → 只删第 2 行（钥匙），宝石还在。

    走过的界面：「清单 ›」小窗 → 第 2 行（钥匙）行尾的 ✕。
    """
    controller, engine, window = _open_sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1, "icon": "gem_red"},
        {"name": "红钥匙", "effect": "", "count": 1, "icon": "key_red"}])
    rows = helpers.find_all(window, "floorItemDelete")
    helpers.click_item(window, rows[1])

    assert [i["name"] for i in _items(window)] == ["红宝石"]


# ---- 数量那个上下箭头（NumberStepper）----

def test_item_count_arrow_increments_and_commits():
    """测什么：点上箭头 +1、点下箭头 -1，都真的落库（不是只改界面）。

    走过的界面：「清单 ›」小窗 → 资源行数量旁边的上/下箭头（点三次）。
    """
    controller, engine, window = _open_sheet(items=[
        {"name": "红宝石", "effect": "攻击力 +1", "count": 3, "icon": "gem_red"}])

    helpers.click_item(window, helpers.find_item(window, "floorItemCountUp"))
    helpers.APP.processEvents()
    assert _items(window)[0]["count"] == 4

    helpers.click_item(window, helpers.find_item(window, "floorItemCountDown"))
    helpers.APP.processEvents()
    assert _items(window)[0]["count"] == 3

    helpers.click_item(window, helpers.find_item(window, "floorItemCountDown"))
    helpers.APP.processEvents()
    assert _items(window)[0]["count"] == 2
