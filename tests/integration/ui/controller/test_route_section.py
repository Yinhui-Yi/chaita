"""主界面「路线」卡（**集成测试**，真 Controller + 真 QML，点真控件）。

路线存在起点层名下、跨层的每格带自己的层，所以不再放在「这一层」清单里，
而是在主界面单独一张卡里把**所有层**的路线统一列出来。

标准见 `tests/integration/README.md`。断言读公开属性（`routeWindow / routeFloor / routeIndex /
routeCollapsed`、层记录里的 `routes`）和界面文字。
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from ... import helpers


def _window(routes_by_floor):
    """起真 Controller + QML，摆好各层的路线。"""
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._map_history = [
        {"floor": floor, "url": "", "mons": [], "items": [],
         "grid": {"cells": []}, "routes": list(routes)}
        for floor, routes in routes_by_floor.items()]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    return controller, engine, window


def _rows(window):
    return helpers.find_all(window, "routeRow")


def _texts(window, name):
    return [item.property("text") for item in helpers.find_all(window, name)]


SAME = {"at": "10:00", "cells": [{"row": 0, "col": 0}]}
CROSS = {"at": "10:05", "memo": "先上楼", "cells": [
    {"row": 0, "col": 0, "floor": "通天塔1"},
    {"row": 3, "col": 3, "floor": "通天塔2"},
    {"row": 1, "col": 1, "floor": "通天塔3"}]}


def test_所有层的路线统一列出_跨层的写起点到终点():
    """测什么：两层各有路线时全部列在一张卡里；同层只写层号，跨层写「起点 → 终点」并带「跨 N 层」。

    走过的界面：主界面「路线」卡。
    """
    controller, engine, window = _window({"通天塔1": [SAME, CROSS],
                                           "通天塔2": [SAME]})

    assert len(_rows(window)) == 3
    assert _texts(window, "routeWhere") == ["1层", "1层 → 3层", "2层"]
    cross_chips = [chip for chip in helpers.find_all(window, "routeCross")
                   if chip.isVisible()]
    assert [helpers.texts_of(chip) for chip in cross_chips] == [["跨 3 层"]]
    assert helpers.find_item(window, "routeAgg").property("text") == "3 条"


def test_没有路线时给一句提示_有路线就不出现():
    """测什么：空的时候说清怎么拖出一条；有路线后提示消失。

    走过的界面：主界面「路线」卡。
    """
    controller, engine, window = _window({"通天塔1": []})
    hint = helpers.find_item(window, "routeCardEmpty")
    assert hint.isVisible() and "长按玩家" in hint.property("text")
    assert _rows(window) == []

    controller._map_history[0]["routes"] = [SAME]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    assert not helpers.find_item(window, "routeCardEmpty").isVisible()
    assert len(_rows(window)) == 1


def test_点路线打开它的链窗口_带上起点层和序号():
    """测什么：点第二层那条路线 → 链窗口打开的是**那一层**的**那一条**（序号按层内算）。

    走过的界面：主界面「路线」卡 → 路线链窗口。
    """
    controller, engine, window = _window({"通天塔1": [SAME],
                                           "通天塔2": [SAME, CROSS]})
    target = _rows(window)[2]          # 通天塔2 的第二条（层内序号 1）
    helpers.click_item(window, [m for m in helpers.find_all(window, "routeOpen")
                                if m.parentItem() == target][0])
    helpers.APP.processEvents()

    assert window.property("routeFloor") == "通天塔2"
    assert window.property("routeIndex") == 1


def test_点叉只删那一条():
    """测什么：删除按钮删的是它那一行的路线，别的层、别的条不动。

    走过的界面：主界面「路线」卡。
    """
    controller, engine, window = _window({"通天塔1": [SAME],
                                           "通天塔2": [SAME, CROSS]})
    target = _rows(window)[1]          # 通天塔2 的第一条
    helpers.click_item(window, [b for b in helpers.find_all(window, "routeRowDelete")
                                if b.parentItem() == target][0])
    helpers.APP.processEvents()

    kept = {entry["floor"]: [r.get("memo", "") for r in entry["routes"]]
            for entry in controller._map_history}
    assert kept == {"通天塔1": [""], "通天塔2": ["先上楼"]}
    assert len(_rows(window)) == 2


def test_备注框回车保存到起点层的那条路线():
    """测什么：跨层路线的备注写进它**起点层**那条记录里；回车才保存。

    走过的界面：主界面「路线」卡的备注框。
    """
    controller, engine, window = _window({"通天塔1": [SAME]})
    field = helpers.find_item(window, "routeMemo")
    helpers.focus_field(field)
    field.setProperty("text", "走这条")
    helpers.APP.processEvents()
    helpers.APP.sendEvent(field.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()

    assert controller._map_history[0]["routes"][0]["memo"] == "走这条"
    # 计算那半截仍然是实时算出来的（没被写进备注）
    assert window.routeStatsFor("通天塔1", 0) == "血 1000 · 攻 90 · 防 30 · 魔防 10"


def test_路线行的数值是实时算出来的_不是存下来的文字():
    """测什么：路线第二行左边写的是现算的 血/攻/防/魔防，和 `routeStatsFor` 一致。

    走过的界面：主界面「路线」卡。
    """
    controller, engine, window = _window({"通天塔1": [SAME]})

    text = helpers.find_item(window, "routeComputed").property("text")

    assert text == window.routeStatsFor("通天塔1", 0)
    assert text.startswith("血 ")


def test_点标题收起和展开路线卡():
    """测什么：点「路线」标题 → 路线行和提示都藏起来，只剩标题行；再点恢复。

    走过的界面：主界面「路线」卡标题行。
    """
    controller, engine, window = _window({"通天塔1": [SAME]})
    card = helpers.find_item(window, "routeSectionCard")
    expanded = card.height()
    assert window.property("routeCollapsed") is False

    helpers.click_item(window, helpers.find_item(window, "routeSectionHead"))
    helpers.APP.processEvents()
    assert window.property("routeCollapsed") is True
    assert not helpers.find_item(window, "routeCardFlick").isVisible()
    assert helpers.wait_for(lambda: card.height() < expanded)

    helpers.click_item(window, helpers.find_item(window, "routeSectionHead"))
    assert window.property("routeCollapsed") is False
    assert helpers.wait_for(lambda: round(card.height()) == round(expanded))


def test_路线很多时卡里滚动_不超过四条的高度():
    """测什么：路线多了卡的高度封顶（4 条），多的在卡里滚，不把主窗口撑爆。

    走过的界面：主界面「路线」卡。
    """
    controller, engine, window = _window({"通天塔1": [SAME] * 8})
    flick = helpers.find_item(window, "routeCardFlick")
    row_h = _rows(window)[0].height()

    assert len(_rows(window)) == 8
    assert round(flick.height()) == round(4 * row_h)
    assert flick.property("contentHeight") > flick.height()
