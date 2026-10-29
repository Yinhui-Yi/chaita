"""桌面命中测试单元测试（`chaita/ui/toolkit/desktop.py`）。

真值来自规则：WM_NCHITTEST 按窗口边缘命中四角/四边，中间和别的消息都不接管。
ctypes MSG 用真结构造出来，窗口用最小 fake。
"""

import ctypes
from ctypes import wintypes

import chaita.ui.toolkit.desktop as desk


class _Screen:
    def devicePixelRatio(self):
        return 1.0


class _Geo:
    def __init__(self, x, y, w, h):
        self._ = (x, y, w, h)

    def x(self):
        return self._[0]

    def y(self):
        return self._[1]

    def width(self):
        return self._[2]

    def height(self):
        return self._[3]


class _Window:
    def screen(self):
        return _Screen()

    def geometry(self):
        return _Geo(100, 100, 400, 400)


def _handle(x, y, message=0x0084, hwnd=0x1234):
    hit = desk.NativeHitTest.__new__(desk.NativeHitTest)
    hit._window = _Window()
    hit._hwnd = 0x1234
    msg = wintypes.MSG()
    msg.message = message
    msg.hWnd = hwnd
    msg.lParam = (y << 16) | x
    return hit._handle(ctypes.addressof(msg))


def test_hit_corners():
    assert _handle(100, 100) == (True, desk._HTTOPLEFT)
    assert _handle(499, 100) == (True, desk._HTTOPRIGHT)
    assert _handle(100, 499) == (True, desk._HTBOTTOMLEFT)
    assert _handle(499, 499) == (True, desk._HTBOTTOMRIGHT)


def test_hit_edges():
    assert _handle(250, 100) == (True, desk._HTTOP)
    assert _handle(100, 250) == (True, desk._HTLEFT)
    assert _handle(499, 250) == (True, desk._HTRIGHT)
    assert _handle(250, 499) == (True, desk._HTBOTTOM)


def test_hit_center_and_other_messages_not_handled():
    assert _handle(250, 250) == (False, 0)
    assert _handle(250, 100, message=0x0085) == (False, 0)  # 非 NCHITTEST


def test_hit_wrong_window_not_handled():
    assert _handle(250, 100, hwnd=0x9999) == (False, 0)


def test_hit_null_message_not_handled():
    hit = desk.NativeHitTest.__new__(desk.NativeHitTest)
    hit._window = _Window()
    hit._hwnd = 0x1234
    assert hit._handle(0) == (False, 0)


def test_focus_window_of_process_rejects_invalid_pid():
    """PID 不合法就直接 False，不去枚举窗口（0 在 Win32 里有"当前进程"的意思）。"""
    assert desk.focus_window_of_process(0) is False
    assert desk.focus_window_of_process(-5) is False


def test_focus_window_of_process_finds_nothing_for_unknown_pid():
    """枚举真的跑一遍：这个 PID 没有进程，不该找到窗口、也不该抛异常。"""
    assert desk.focus_window_of_process(0x7FFFFFF0) is False
    assert desk._top_windows_of(0x7FFFFFF0) == []
    assert desk._main_window_of(0x7FFFFFF0) == 0


# ---- 主窗口怎么挑 / 怎么叫到前面 ----

def test_main_window_prefers_app_title(monkeypatch):
    monkeypatch.setattr(desk, "_top_windows_of",
                        lambda pid: [("某一层", 5), (desk.APP_TITLE, 9)])
    assert desk._main_window_of(123) == 9


def test_main_window_falls_back_to_topmost_of_pid(monkeypatch):
    monkeypatch.setattr(desk, "_top_windows_of",
                        lambda pid: [("某一层", 5), ("伤害计算", 7)])
    assert desk._main_window_of(123) == 5


def test_main_window_none_when_nothing(monkeypatch):
    monkeypatch.setattr(desk, "_top_windows_of", lambda pid: [])
    assert desk._main_window_of(123) == 0


def test_focus_window_does_the_topmost_dance(monkeypatch):
    """抢前台会被系统拒绝，所以顺序是：还原 → 置顶 → 取消置顶 → 要前台。"""
    calls = []
    user32 = type("User32", (), {
        "ShowWindow": staticmethod(lambda h, c: calls.append(("ShowWindow", h, c))),
        "SetWindowPos": staticmethod(
            lambda h, after, x, y, cx, cy, flags:
            calls.append(("SetWindowPos", h, after))),
        "SetForegroundWindow": staticmethod(
            lambda h: calls.append(("SetForegroundWindow", h))),
    })
    monkeypatch.setattr(desk.ctypes, "windll",
                        type("Windll", (), {"user32": user32}), raising=False)
    monkeypatch.setattr(desk, "_main_window_of", lambda pid: 9)

    assert desk.focus_window_of_process(4242) is True
    assert calls == [
        ("ShowWindow", 9, desk._SW_RESTORE),
        ("SetWindowPos", 9, desk._HWND_TOPMOST),
        ("SetWindowPos", 9, desk._HWND_NOTOPMOST),
        ("SetForegroundWindow", 9)]


def test_focus_window_without_window_does_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(desk, "_main_window_of", lambda pid: 0)
    monkeypatch.setattr(desk.ctypes, "windll",
                        type("Windll", (), {"user32": type("U", (), {
                            "ShowWindow": staticmethod(
                                lambda *a: calls.append(a))})}),
                        raising=False)
    assert desk.focus_window_of_process(4242) is False
    assert calls == []


def test_cursor_helpers_go_through_win32api(monkeypatch):
    import sys
    pressed = {"down": True}
    fake = type("FakeWin32", (), {
        "GetCursorPos": staticmethod(lambda: (10, 20)),
        "GetAsyncKeyState": staticmethod(
            lambda vk: 0x8000 if pressed["down"] else 0),
    })
    monkeypatch.setitem(sys.modules, "win32api", fake)

    assert desk._cursor_pos() == (10, 20)
    assert desk._cursor_down() is True
    pressed["down"] = False
    assert desk._cursor_down() is False
