"""窗口动画/几何/前台采样单元测试（`chaita/ui/controller/window.py`）。

真值来自规则：OutCubic 插值到目标、宽高为 0 表示别覆盖尺寸、前台是 python 不算。
"""

from unittest.mock import Mock

from chaita.ui.controller.window import WindowMixin


class _Win:
    def __init__(self):
        self.props = {"width": 100, "height": 200}

    def setProperty(self, k, v):
        self.props[k] = int(v)

    def property(self, k):
        return self.props.get(k, 0)


class _Anim:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


def _mix():
    c = WindowMixin.__new__(WindowMixin)
    c._win = _Win()
    c._anim = _Anim()
    c._anim_from = (100, 200)
    c._anim_to = (400, 800)
    c._anim_ms = 100
    c._anim_start = 0.0
    c.sizeAnimDone = Mock()
    return c


def test_tick_size_finishes_at_target(monkeypatch):
    monkeypatch.setattr("time.monotonic", lambda: 1.0)
    c = _mix()
    c._tick_size()
    assert c._win.props["width"] == 400
    assert c._win.props["height"] == 800
    assert c._anim.stopped
    assert c.sizeAnimDone.emit.called


def test_tick_size_midpoint_outcubic(monkeypatch):
    monkeypatch.setattr("time.monotonic", lambda: 0.5)
    c = _mix()
    c._anim_from = (0, 0)
    c._anim_to = (100, 0)
    c._anim_ms = 1000
    c._anim_start = 0.0
    c._tick_size()
    # eased = 1-(1-0.5)^3 = 0.875 → w = round(87.5) = 88
    assert c._win.props["width"] == 88


def test_remember_window_records_geometry():
    c = WindowMixin.__new__(WindowMixin)
    c._geometry_ready = True
    c._pending_geometry = None
    c._state_timer = Mock()
    c.rememberWindow(10, 20, 300, 400)
    assert c._pending_geometry == {"x": 10, "y": 20, "width": 300,
                                   "height": 400}
    assert c._state_timer.start.called


def test_remember_window_zero_size_drops_size():
    c = WindowMixin.__new__(WindowMixin)
    c._geometry_ready = True
    c._state_timer = Mock()
    c.rememberWindow(10, 20, 0, 0)
    assert c._pending_geometry == {"x": 10, "y": 20}


def test_remember_window_not_ready_is_noop():
    c = WindowMixin.__new__(WindowMixin)
    c._geometry_ready = False
    c._pending_geometry = None
    c._state_timer = Mock()
    c.rememberWindow(10, 20, 300, 400)
    assert c._pending_geometry is None
    assert not c._state_timer.start.called


def test_flush_ui_state_merges(monkeypatch):
    import chaita.ui.controller.window as win
    monkeypatch.setattr(win, "_load_ui_state",
                        lambda: {"x": 1, "y": 2, "width": 300})
    saved = []
    monkeypatch.setattr(win, "_save_ui_state", lambda d: saved.append(d))
    c = WindowMixin.__new__(WindowMixin)
    c._pending_geometry = {"x": 5, "y": 6}
    c._flush_ui_state()
    assert saved[0] == {"x": 5, "y": 6, "width": 300}
    assert c._pending_geometry is None


class _PinWin:
    def __init__(self):
        self.props = {}

    def setProperty(self, k, v):
        self.props[k] = v

    def winId(self):
        return 4321


def _pin_mix(monkeypatch, saved_state):
    """一个只带窗口的 WindowMixin；Win32 置顶和状态文件都换成记录器。"""
    import chaita.ui.controller.window as win
    topmost_calls, saved = [], []
    monkeypatch.setattr(win.desktop, "set_topmost",
                        lambda hwnd, on: topmost_calls.append((hwnd, on)) or True)
    monkeypatch.setattr(win, "_load_ui_state", lambda: dict(saved_state))
    monkeypatch.setattr(win, "_save_ui_state", lambda data: saved.append(data))
    c = WindowMixin.__new__(WindowMixin)
    c._win = _PinWin()
    return c, topmost_calls, saved


def test_set_pinned_切Win32置顶_更新窗口属性_并记住(monkeypatch):
    c, topmost_calls, saved = _pin_mix(monkeypatch, {"x": 1, "y": 2})

    c.setPinned(True)

    assert topmost_calls == [(4321, True)]
    assert c._win.props["pinned"] is True
    assert saved == [{"x": 1, "y": 2, "pinned": True}]     # 位置不能被冲掉

    c.setPinned(False)
    assert topmost_calls[-1] == (4321, False)
    assert saved[-1]["pinned"] is False


def test_restore_pinned_只在上次记着置顶时才置顶(monkeypatch):
    c, topmost_calls, _ = _pin_mix(monkeypatch, {"pinned": True})
    c.restorePinned()
    assert topmost_calls == [(4321, True)]
    assert c._win.props["pinned"] is True

    c, topmost_calls, _ = _pin_mix(monkeypatch, {"x": 1})      # 没记录 = 默认不置顶
    c.restorePinned()
    assert topmost_calls == []
    assert "pinned" not in c._win.props


def test_set_pinned_先切主窗口置顶_再改pinned属性(monkeypatch):
    """子窗口的置顶标志绑定 `pinned`，改属性会让 Qt 重建子窗口；这之后再给主窗口设置顶
    会「返回成功、其实没生效」（实测），所以必须先设主窗口。"""
    import chaita.ui.controller.window as win
    c, _, _ = _pin_mix(monkeypatch, {})
    events = []
    monkeypatch.setattr(win.desktop, "set_topmost",
                        lambda hwnd, on: events.append("topmost") or True)
    c._win.setProperty = lambda key, value: events.append("prop:" + key)

    c.setPinned(True)

    assert events == ["topmost", "prop:pinned"]


def test_set_chat_collapsed_更新窗口属性_并记住(monkeypatch):
    c, _, saved = _pin_mix(monkeypatch, {"x": 1, "pinned": True})

    c.setChatCollapsed(True)

    assert c._win.props["chatCollapsed"] is True
    assert saved == [{"x": 1, "pinned": True, "chatCollapsed": True}]   # 别的状态不能被冲掉

    c.setChatCollapsed(False)
    assert saved[-1]["chatCollapsed"] is False


def test_restore_chat_collapsed_只在上次收起过才收起(monkeypatch):
    c, _, _ = _pin_mix(monkeypatch, {"chatCollapsed": True})
    c.restoreChatCollapsed()
    assert c._win.props["chatCollapsed"] is True

    c, _, _ = _pin_mix(monkeypatch, {"x": 1})            # 没记录 = 展开
    c.restoreChatCollapsed()
    assert "chatCollapsed" not in c._win.props


def test_set_route_collapsed_更新窗口属性_并记住_不冲掉别的状态(monkeypatch):
    c, _, saved = _pin_mix(monkeypatch, {"x": 1, "chatCollapsed": True})

    c.setRouteCollapsed(True)

    assert c._win.props["routeCollapsed"] is True
    assert saved == [{"x": 1, "chatCollapsed": True, "routeCollapsed": True}]

    c.setRouteCollapsed(False)
    assert saved[-1]["routeCollapsed"] is False


def test_restore_route_collapsed_只在上次收起过才收起(monkeypatch):
    c, _, _ = _pin_mix(monkeypatch, {"routeCollapsed": True})
    c.restoreRouteCollapsed()
    assert c._win.props["routeCollapsed"] is True

    c, _, _ = _pin_mix(monkeypatch, {"chatCollapsed": True})   # 别的开关不串
    c.restoreRouteCollapsed()
    assert "routeCollapsed" not in c._win.props


def test_set_pinned_没有窗口也不报错(monkeypatch):
    c, topmost_calls, _ = _pin_mix(monkeypatch, {})
    c._win = None
    c.setPinned(True)
    assert topmost_calls == []


def test_sample_foreground_skips_python(monkeypatch):
    import chaita.game.winutil as wu
    monkeypatch.setattr(wu, "foreground_top_window", lambda: 1)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "pythonw.exe")
    c = WindowMixin.__new__(WindowMixin)
    c._closing = False
    c._last_foreground = ""
    c._sample_foreground()
    assert c._last_foreground == ""


def test_sample_foreground_records_browser(monkeypatch):
    import chaita.game.winutil as wu
    monkeypatch.setattr(wu, "foreground_top_window", lambda: 1)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "msedge.exe")
    monkeypatch.setattr(wu, "remember_foreground", lambda hwnd: None)
    c = WindowMixin.__new__(WindowMixin)
    c._closing = False
    c._last_foreground = ""
    c._sample_foreground()
    assert c._last_foreground == "msedge.exe"


# ---- 边界：不该动的时候什么都不做 ----

def test_sample_foreground_skips_when_closing(monkeypatch):
    import chaita.game.winutil as wu
    monkeypatch.setattr(wu, "foreground_top_window",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("退出中不该再采样前台")))
    c = WindowMixin.__new__(WindowMixin)
    c._closing = True
    c._last_foreground = ""
    c._sample_foreground()
    assert c._last_foreground == ""


def test_sample_foreground_skips_without_window_or_process(monkeypatch):
    import chaita.game.winutil as wu
    c = WindowMixin.__new__(WindowMixin)
    c._closing = False
    c._last_foreground = "old"

    monkeypatch.setattr(wu, "foreground_top_window", lambda: None)
    c._sample_foreground()
    assert c._last_foreground == "old"

    monkeypatch.setattr(wu, "foreground_top_window", lambda: 5)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "")
    c._sample_foreground()
    assert c._last_foreground == "old"


def test_animate_size_and_tick_size_without_window():
    c = _mix()
    c._win = None
    c.animateSize(300, 300, 100)          # 不该炸
    c._tick_size()                        # 没有窗口就把动画停掉
    assert c._anim.stopped


def test_flush_ui_state_without_pending_is_noop(monkeypatch):
    import chaita.ui.controller.window as win
    saved = []
    monkeypatch.setattr(win, "_save_ui_state", lambda d: saved.append(d))
    monkeypatch.setattr(win, "_load_ui_state",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("没有待写的数据不该去读旧状态")))
    c = WindowMixin.__new__(WindowMixin)
    c._pending_geometry = None

    c._flush_ui_state()

    assert saved == []                      # 一个字节都不落盘


def test_begin_shutdown_stops_timers_and_joins_threads():
    import time as time_mod
    stopped = []

    class Timer:
        def __init__(self, name):
            self.name = name

        def stop(self):
            stopped.append(self.name)

    joined = []

    class Thread:
        def join(self, timeout=None):
            joined.append(timeout)

    c = WindowMixin.__new__(WindowMixin)
    c._closing = False
    c._poll = Timer("poll")
    c._timer = Timer("drag")
    c._state_timer = Timer("state")
    c._mon_drag_timer = Timer("mon")
    c._threads = [Thread()]

    c._begin_shutdown()

    assert c._closing is True
    assert stopped == ["poll", "drag", "state", "mon"]
    assert len(joined) == 1
    assert 0 < joined[0] <= 2.0
    # 再调一次不该再动（QML 关窗 + App 退出会各来一次）
    stopped.clear()
    c._begin_shutdown()
    assert stopped == []


def test_begin_shutdown_survives_timer_error():
    class BadTimer:
        def stop(self):
            raise RuntimeError("已经没了")

    c = WindowMixin.__new__(WindowMixin)
    c._closing = False
    c._poll = c._timer = c._state_timer = c._mon_drag_timer = BadTimer()
    c._threads = []
    c._begin_shutdown()                   # 不抛
    assert c._closing is True


def test_quit_saves_session_then_quits(monkeypatch):
    import chaita.ui.controller.window as win
    saved = []
    monkeypatch.setattr(win, "_save_session",
                        lambda monsters, floors: saved.append(floors))

    class App:
        def __init__(self):
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    app = App()
    monkeypatch.setattr(win.QGuiApplication, "instance",
                        staticmethod(lambda: app), raising=False)

    c = WindowMixin.__new__(WindowMixin)
    c._closing = False
    c._monsters = [{"name": "血蚊"}]
    c._map_history = [{"floor": "1"}]
    c._poll = c._timer = c._state_timer = c._mon_drag_timer = _Anim()
    c._threads = []

    c.quit()

    assert saved == [[{"floor": "1"}]]     # 先存盘
    assert c._closing is True
    assert app.quit_called is True


def test_drag_start_without_window_is_noop():
    c = WindowMixin.__new__(WindowMixin)
    c._win = None
    c._timer = Mock()
    c.dragStart(10, 20)
    assert not c._timer.start.called


def test_tick_drag_moves_window(monkeypatch):
    import sys
    import chaita.ui.controller.window as win

    fake = type("FakeWin32", (), {"GetCursorPos": staticmethod(lambda: (300, 400))})
    monkeypatch.setitem(sys.modules, "win32api", fake)

    class Screen:
        def devicePixelRatio(self):
            return 1.0

    monkeypatch.setattr(win.QGuiApplication, "primaryScreen",
                        staticmethod(lambda: Screen()), raising=False)

    c = WindowMixin.__new__(WindowMixin)
    c._win = _Win()
    c._drag_active = True
    c._drag_offset = (10, 20)
    c._last_pos = None

    c._tick_drag()
    assert (c._win.props["x"], c._win.props["y"]) == (290, 380)
    assert c._last_pos == (290, 380)

    # 位置没变就别再写（一次拖动会 tick 很多次，免得刷屏）
    c._win.props["x"] = 0
    c._tick_drag()
    assert c._win.props["x"] == 0


def test_tick_drag_inactive_does_nothing(monkeypatch):
    import sys
    import chaita.ui.controller.window as win

    fake = type("FakeWin32", (), {"GetCursorPos": staticmethod(
        lambda: (_ for _ in ()).throw(AssertionError("没在拖就别读光标")))})
    monkeypatch.setitem(sys.modules, "win32api", fake)
    c = WindowMixin.__new__(WindowMixin)
    c._win = _Win()
    c._drag_active = False

    c._tick_drag()

    assert c._win.props == {"width": 100, "height": 200}   # 窗口一动不动
