"""置顶开关 + 任务栏（**集成测试**，真窗口、真 Win32 样式位）。

规则：主窗口是普通顶层窗口（任务栏 / Alt+Tab 里有它），**默认不置顶**；导航条上的
「置顶」点一下才永远在最前面，再点取消；子窗口挂在主窗口名下，跟着它一起置顶/取消。

标准见 `tests/integration/README.md`。窗口状态文件在测试里一律关掉（不写 logs/ui_state.json）。
"""

import ctypes

from PySide6.QtCore import Qt

from ... import helpers

_GWL_EXSTYLE = -20
_WS_EX_TOPMOST = 0x00000008
_WS_EX_TOOLWINDOW = 0x00000080


def _exstyle(window):
    return ctypes.windll.user32.GetWindowLongW(int(window.winId()), _GWL_EXSTYLE)


def _topmost(window):
    return bool(_exstyle(window) & _WS_EX_TOPMOST)


def test_主窗口进任务栏_默认不置顶():
    """测什么：主窗口不是工具窗口（任务栏里有它）、没有永远置顶的标志，启动时也没被置顶。

    走过的界面：主窗口本身（窗口标志 + Win32 扩展样式）。
    """
    controller, engine, window = helpers.make_controller()
    helpers.APP.processEvents()

    assert (window.flags() & Qt.WindowType_Mask) == Qt.Window     # 不是 Qt.Tool
    assert not (window.flags() & Qt.WindowStaysOnTopHint)
    assert not (_exstyle(window) & _WS_EX_TOOLWINDOW)
    assert not _topmost(window)
    assert window.property("pinned") is False
    assert window.title() == "拆塔辅助"


def test_点置顶开关_主窗口和子窗口一起置顶_再点取消():
    """测什么：点导航条「置顶」→ 主窗口和已经开着的伤害计算窗口都变成置顶；再点一下都取消。

    走过的界面：导航条「置顶」→ 导航条 ⚔（先开伤害计算）。
    """
    controller, engine, window = helpers.make_controller()
    helpers.click_item(window, helpers.find_item(window, "battleOpen"))
    battle = window.property("battleWindow")
    battle = battle.toQObject() if hasattr(battle, "toQObject") else battle
    assert helpers.wait_for(lambda: battle is not None and battle.isVisible())
    assert not _topmost(battle)

    pin = helpers.find_item(window, "pinToggle")
    helpers.click_item(window, pin)
    assert window.property("pinned") is True
    assert _topmost(window)
    assert _topmost(battle)

    helpers.click_item(window, pin)
    assert window.property("pinned") is False
    assert not _topmost(window)
    assert not _topmost(battle)


def test_先置顶再开子窗口_子窗口也在最上面():
    """测什么：已经置顶的时候再点开伤害计算 → 新开的窗口也得在最上面，不会被别的应用盖住。

    走过的界面：导航条「置顶」→ 导航条 ⚔。
    """
    controller, engine, window = helpers.make_controller()
    helpers.click_item(window, helpers.find_item(window, "pinToggle"))
    try:
        helpers.click_item(window, helpers.find_item(window, "battleOpen"))
        battle = window.property("battleWindow")
        battle = battle.toQObject() if hasattr(battle, "toQObject") else battle
        assert helpers.wait_for(lambda: battle is not None and battle.isVisible())
        assert _topmost(battle)
    finally:
        controller.setPinned(False)
