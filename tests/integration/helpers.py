"""集成测试的 QML 辅助：起 Controller + 引擎、按 objectName 找/点控件。

这不是测试逻辑，是测试基座（每个集成用例都要用）。

写集成测试之前先看这几条 —— 全是这个仓库里**真的踩过**的坑，踩了以后
现象都很像"代码坏了"，其实都是测试写法的问题：

1. **`find_item` 是遍历顺序，`find_all` 才是屏幕位置顺序。**
   要点"第一个格子/第一行"，必须用 `find_all(...)[0]`。用 find_item 可能先拿到
   第二格，于是改的是别人的数据，断言全红（路线链改参数那次就是这么翻车的）。

2. **缓存属性改完要发信号。** `controller.statusData / monRows / floorList /
   sheetMons` 这些是 QML 侧缓存的，直接改 `controller._last_status / _monsters /
   _map_history` 不发信号，界面还是上一轮的名单；而且**隐藏的行上的控件根本点不到**。
   规则：改完立刻 `controller.xxxChanged.emit()`（statusTextChanged /
   monstersChanged / mapHistoryChanged）。

3. **从 QML 拿到的对象要钉住**（`_hold()` 已做）：PySide 有时把 QML 控件的所有权
   判给 Python，wrapper 被回收会把 C++ 对象一起删掉，之后任何访问都是
   "Internal C++ object already deleted"。同理 **engine 必须活着**（它被回收 =
   窗口没了），所以 `make_controller()` 返回三元组，别只接窗口。

4. **别碰真环境**：剪贴板用 `fake_clipboard()`、游戏窗口用
   `fake_game_window()`；`_poll`（120ms 前台采样）和 `_state_timer` 已经在
   `make_controller()` 里停掉了。碰了真环境 = 结果取决于跑测试那一刻机器上开着什么。

5. **点击/输入前先 pump 事件**（`click_item` 已做），窗口刚建出来时控件是 0×0 的；
   一个动作没命中就**重试并断言条件**（`_click_until` 那种写法），别默默往下走。

6. **断言别依赖环境状态**：光标在哪、悬停是什么、窗口 z 序都不该进断言；
   断言规则本身（比如"出界之后不会出现 13 格以外的坐标"）。

7. **测试不许写用户的东西**：不写 `logs/last_session.json` / `logs/ui_state.json` /
   `assets/`，一律 monkeypatch 掉（`setattr(os, "remove", ...)` 之类）。
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402,F401

from chaita.game import towers  # noqa: E402
from chaita.ui import main as ov  # noqa: E402

APP = None

# **必须留强引用**：PySide 有时会把 QML 控件的所有权判给 Python，wrapper 被回收时
# 连 QML 对象一起删掉 —— 之后再碰就是 "Internal C++ object already deleted"，
# 而且炸的地方和真正的原因（上一行里那个临时变量）离得十万八千里。
# 一整轮测试就那几扇窗，全留着不心疼。
_KEEP_ALIVE = []


def _hold(obj):
    """把一个从 QML 拿到的对象钉住，别让 Python 回收它。"""
    if obj is not None:
        _KEEP_ALIVE.append(obj)
    return obj


def ensure_app():
    global APP
    if APP is None:
        APP = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    return APP


def make_controller():
    """起一个真 Controller + QML 引擎，返回 (controller, engine, window)。"""
    ensure_app()
    controller = ov.Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    ov.load_into(engine)
    roots = engine.rootObjects()
    if not roots:
        raise RuntimeError("QML 加载失败")
    window = roots[0]
    controller.attach(window)
    for name, value in (("itemBase", ov.ITEM_BASE), ("iconBase", ov.ICON_BASE),
                        ("heroIcon", ov.HERO_ICON), ("collapsed", False)):
        window.setProperty(name, value)
    controller._last_foreground = towers.H5_MOTA.process
    # 关掉前台采样定时器（120ms）：它会把 `_last_foreground` 改成"跑测试的那个
    # 浏览器/终端"，于是任何依赖前台的判定都变成看运气（踩过两次）。
    # 顺便停掉窗口状态定时器：别让测试把 logs/ui_state.json 写脏。
    controller._poll.stop()
    controller._state_timer.stop()
    return controller, engine, window


def wait_for(predicate, timeout=20.0, step=0.05):
    ensure_app()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        APP.processEvents()
        if predicate():
            return True
        time.sleep(step)
    APP.processEvents()
    return predicate()


def host_windows(window):
    """主窗口 + 它开出来的「这一层」/伤害计算/路线链真窗口。"""
    hosts = [window]
    names = window.property("floorWindows")
    names = names.toVariant() if hasattr(names, "toVariant") else names
    for name in names or []:
        try:
            sheet = window.floorSheetOf(str(name))
        except (RuntimeError, AttributeError):
            continue
        if sheet is not None:
            hosts.append(sheet)
    try:
        battle = window.property("battleWindow")
        if hasattr(battle, "toQObject"):
            battle = battle.toQObject()
        if battle is not None:
            hosts.append(battle)
    except (RuntimeError, AttributeError):
        pass
    try:
        route = window.property("routeWindow")
        if hasattr(route, "toQObject"):
            route = route.toQObject()
        if route is not None:
            hosts.append(route)
    except (RuntimeError, AttributeError):
        pass
    return hosts


def find_item(window, name):
    """按 objectName 找一个控件（遍历主窗口 + 所有子窗口）。"""
    if isinstance(window, QQuickItem):
        stack = list(window.childItems())
        while stack:
            node = stack.pop()
            if node.objectName() == name:
                return _hold(node)
            stack.extend(node.childItems())
        return None
    for host in host_windows(window):
        stack = list(host.contentItem().childItems())
        while stack:
            node = stack.pop()
            if node.objectName() == name:
                return _hold(node)
            stack.extend(node.childItems())
    return None


def find_all(window, name):
    """按 objectName 找所有看得见的同名控件，按屏幕位置（上→下、左→右）排序。"""
    out = []
    roots = [window] if isinstance(window, QQuickItem) else list(host_windows(window))
    for host in roots:
        if isinstance(host, QQuickItem):
            stack = list(host.childItems())[::-1]
        else:
            stack = list(host.contentItem().childItems())[::-1]
        while stack:
            node = stack.pop()
            if node.objectName() == name and node.isVisible():
                out.append(_hold(node))
            stack.extend(list(node.childItems())[::-1])
    return sorted(out, key=lambda item: (
        round(item.mapToScene(QPointF(0, 0)).y(), 1),
        round(item.mapToScene(QPointF(0, 0)).x(), 1)))


def window_of(window, item):
    """这个控件长在哪个真窗口里（主窗口还是某一扇子窗口）。

    直接用 `item.window()`：QQuickItem 顺着 parentItem 走不到 QQuickWindow
    （contentItem 的 parentItem 是 None），但它能直接告诉你自己在哪扇窗里。
    """
    if item is None:
        return window
    owner = item.window() if hasattr(item, "window") else None
    return owner if isinstance(owner, QQuickWindow) else window


def click_item(window, item):
    """真的点一下这个控件（合成鼠标事件，等价于用户点）。

    先等布局：刚建出来的窗口/delegate 还没走完布局，控件是 0×0、位置 0,0，
    拿它算出来的点击点会落到窗口外面 —— "点了等于没点"，而且**不报错**，
    于是偶尔红一次、重跑又绿（这类 flaky 已经踩到三次了）。
    """
    from PySide6.QtGui import QMouseEvent
    ensure_app().processEvents()
    if item is None:
        raise AssertionError("要点的控件没找到")
    wait_for(lambda: item.width() > 0 and item.height() > 0, timeout=1.0)
    target = window_of(window, item)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        APP.sendEvent(target, QMouseEvent(kind, point, point, Qt.LeftButton,
                                          Qt.LeftButton, Qt.NoModifier))
    APP.processEvents()


class _FakeClipboard:
    def __init__(self):
        self.value = ""

    def setText(self, text):
        self.value = str(text)

    def text(self):
        return self.value


def fake_clipboard(monkeypatch):
    """把系统剪贴板换成内存里的。

    测试**不许碰用户真剪贴板**：它既是环境依赖（有的环境没剪贴板），又会把用户
    正在复制的东西冲掉。`controller.clipboardCopy/clipboardText` 仍然是真的，
    只是底下那层换成了这个。
    """
    import chaita.ui.controller.controller as controller_mod
    board = _FakeClipboard()
    fake_app = type("FakeApp", (),
                    {"clipboard": staticmethod(lambda: board)})
    monkeypatch.setattr(controller_mod, "QGuiApplication", fake_app,
                        raising=False)
    return board


def fake_game_window(monkeypatch, process):
    """让"找游戏窗口"这一步只找到这一座塔，别真去问 Windows。

    为什么必须桩：控制器有个 120ms 的前台采样定时器，pump 事件时会把
    `_last_foreground` 覆盖成"正在跑测试的浏览器"，于是下一步按进程名找游戏
    窗口就变成了**环境依赖** —— 机器上开着游戏就过、没开就红。
    """
    from chaita.game import winutil
    monkeypatch.setattr(winutil, "find_window",
                        lambda name: 1 if name == process else None)
    return process


def drop_cells(window, item, payload):
    """把格子数据"拖"到这个控件上松手（合成 enter/move/drop，打到真 DropArea）。

    `payload` 就是一格 `{"row": r, "col": c}`，多选是
    `{"cells": [{"row": r, "col": c}, ...]}` —— 和 QML 里 `Drag.mimeData` 同一份
    格式。平台的真拖拽会话在测试里驱动不了（Drag.Automatic 会进模态循环），
    所以直接合成这三个事件：走的是 QML 的 `onDropped`，不是调 Slot。
    """
    import json
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
    target = window_of(window, item)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    mime = QMimeData()
    mime.setData("application/x-grid-cell",
                 json.dumps(payload).encode("utf-8"))
    for event in (QDragEnterEvent(point.toPoint(), Qt.CopyAction, mime,
                                  Qt.LeftButton, Qt.NoModifier),
                  QDragMoveEvent(point.toPoint(), Qt.CopyAction, mime,
                                 Qt.LeftButton, Qt.NoModifier),
                  QDropEvent(point, Qt.CopyAction, mime,
                             Qt.LeftButton, Qt.NoModifier)):
        APP.sendEvent(target, event)
    APP.processEvents()


def route_window(window):
    """路线链窗口（`win.routeWindow`）；没开就是 None。"""
    value = window.property("routeWindow")
    return value.toQObject() if hasattr(value, "toQObject") else value


def texts_of(item):
    """一个控件里所有文字的 text（不做可见性判断）。"""
    out = []
    stack = list(item.childItems())
    while stack:
        node = stack.pop()
        try:
            text = node.property("text")
        except (RuntimeError, AttributeError):
            text = None
        if text is not None and str(text) != "":
            out.append(str(text))
        stack.extend(node.childItems())
    return out
