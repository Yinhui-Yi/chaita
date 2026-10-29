"""窗口查找单元测试（`chaita/game/winutil.py`）。

真值来自规则：按进程名匹配、最大的优先、前台优先、标题去浏览器噪音。
win32 API 全 stub。
"""

import chaita.game.winutil as wu


# ---- clean_title：纯函数 ----

def test_clean_title_rm_tutorial():
    assert wu.clean_title("教程塔") == "教程塔"


def test_clean_title_edge_strips_shell_noise():
    title = "坐牢成仙 - HTML5魔塔 和另外 14 个页面 - 工作 - Microsoft Edge"
    assert wu.clean_title(title) == "坐牢成仙"


def test_clean_title_noise_only_is_empty():
    assert wu.clean_title("HTML5魔塔 - 其他") == ""


def test_clean_title_noise_in_head():
    assert wu.clean_title("坐牢成仙 和另外 2 个页面") == "坐牢成仙"


def test_clean_title_empty():
    assert wu.clean_title("") == ""


def test_clean_title_strips_zero_width():
    assert wu.clean_title("塔\u200b名") == "塔名"


# ---- 记前台窗口 ----

def test_remember_foreground_sets_and_ignores_falsy():
    wu._REMEMBERED.hwnd = None
    wu.remember_foreground(123)
    assert wu._REMEMBERED.hwnd == 123
    wu.remember_foreground(0)
    wu.remember_foreground(None)
    assert wu._REMEMBERED.hwnd == 123


# ---- process_name / find_window / game_window / window_title ----

def test_process_name_lowercases(monkeypatch):
    monkeypatch.setattr(wu.win32process, "GetWindowThreadProcessId",
                        lambda hwnd: (None, 42))
    monkeypatch.setattr(wu.win32api, "OpenProcess", lambda *a, **k: "h")
    monkeypatch.setattr(wu.win32process, "GetModuleFileNameEx",
                        lambda h, m: "C:/Path/Game.exe")
    assert wu.process_name(1) == "game.exe"


def test_process_name_error_is_empty(monkeypatch):
    monkeypatch.setattr(wu.win32process, "GetWindowThreadProcessId",
                        lambda hwnd: (_ for _ in ()).throw(Exception("x")))
    assert wu.process_name(1) == ""


def test_find_window_returns_largest(monkeypatch):
    monkeypatch.setattr(wu, "list_windows", lambda: [
        (1, "A", "c", 0, 0, 100, 100),   # area 10000
        (2, "B", "c", 0, 0, 200, 200),   # area 40000
    ])
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "game.exe")
    assert wu.find_window("game.exe") == 2


def test_find_window_none_when_no_match(monkeypatch):
    monkeypatch.setattr(wu, "list_windows", lambda: [])
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "game.exe")
    assert wu.find_window("game.exe") is None


def test_game_window_prefers_foreground(monkeypatch):
    monkeypatch.setattr(wu, "list_windows", lambda: [(1, "A", "c", 0, 0, 100, 100)])
    monkeypatch.setattr(wu, "foreground_top_window", lambda: 1)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "game.exe")
    wu._REMEMBERED.hwnd = None
    assert wu.game_window("game.exe") == 1


def test_game_window_empty_process_is_none():
    assert wu.game_window("") is None


def test_window_title(monkeypatch):
    monkeypatch.setattr(wu, "find_window", lambda p: 5)
    monkeypatch.setattr(wu.win32gui, "GetWindowText", lambda hwnd: "标题")
    assert wu.window_title("game.exe") == "标题"


def test_window_title_none(monkeypatch):
    monkeypatch.setattr(wu, "find_window", lambda p: None)
    assert wu.window_title("game.exe") == ""


# ---- list_windows：什么样的窗口才被算进来 ----

def _fake_gui(monkeypatch, rows):
    """rows: {hwnd: (title, rect, visible, cls)}；rect 是异常时传 Exception 实例。"""
    state = {"rows": rows}

    def enum(callback, param):
        for hwnd in state["rows"]:
            callback(hwnd, param)

    monkeypatch.setattr(wu.win32gui, "EnumWindows", enum)
    monkeypatch.setattr(wu.win32gui, "IsWindowVisible",
                        lambda hwnd: state["rows"][hwnd][2])
    monkeypatch.setattr(wu.win32gui, "GetWindowText",
                        lambda hwnd: state["rows"][hwnd][0])

    def get_rect(hwnd):
        rect = state["rows"][hwnd][1]
        if isinstance(rect, Exception):
            raise rect
        return rect

    monkeypatch.setattr(wu.win32gui, "GetWindowRect", get_rect)
    monkeypatch.setattr(wu.win32gui, "GetClassName",
                        lambda hwnd: state["rows"][hwnd][3])
    return state


def test_list_windows_filters_invisible_tiny_and_broken(monkeypatch):
    _fake_gui(monkeypatch, {
        1: ("正常窗口", (0, 0, 800, 600), True, "Cls"),
        2: ("隐藏的", (0, 0, 800, 600), False, "Cls"),
        3: ("   ", (0, 0, 800, 600), True, "Cls"),          # 标题全空白
        4: ("太小的", (0, 0, 100, 600), True, "Cls"),
        5: ("取不到位置", RuntimeError("窗口没了"), True, "Cls"),
    })

    rows = wu.list_windows()

    assert [row[0] for row in rows] == [1]
    assert rows[0][1:] == ("正常窗口", "Cls", 0, 0, 800, 600)


def test_list_windows_keeps_big_enough_square(monkeypatch):
    _fake_gui(monkeypatch, {7: ("刚好够大", (0, 0, 150, 150), True, "C")})
    assert len(wu.list_windows()) == 1


# ---- 前台窗口：取不到就 None ----

def test_foreground_window_errors_are_none(monkeypatch):
    monkeypatch.setattr(wu.win32gui, "GetForegroundWindow",
                        lambda: (_ for _ in ()).throw(RuntimeError("没有前台")))
    assert wu.foreground_top_window() is None

    monkeypatch.setattr(wu.win32gui, "GetForegroundWindow", lambda: 0)
    assert wu.foreground_top_window() is None


def test_foreground_window_walks_up_to_root(monkeypatch):
    monkeypatch.setattr(wu.win32gui, "GetForegroundWindow", lambda: 11)
    monkeypatch.setattr(wu.win32gui, "GetAncestor", lambda hwnd, flag: 22)
    assert wu.foreground_top_window() == 22


def test_foreground_window_falls_back_to_itself(monkeypatch):
    monkeypatch.setattr(wu.win32gui, "GetForegroundWindow", lambda: 11)
    monkeypatch.setattr(wu.win32gui, "GetAncestor",
                        lambda hwnd, flag: (_ for _ in ()).throw(RuntimeError("x")))
    assert wu.foreground_top_window() == 11


# ---- game_window：前台 → 记住的那扇 → 同进程最大的 ----

def test_game_window_uses_remembered_window(monkeypatch):
    monkeypatch.setattr(wu, "list_windows", lambda: [(5, "A", "c", 0, 0, 900, 900)])
    monkeypatch.setattr(wu, "foreground_top_window", lambda: None)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "chrome.exe")
    wu._REMEMBERED.hwnd = 5

    assert wu.game_window("Chrome.exe") == 5      # 大小写不敏感


def test_game_window_ignores_hidden_remembered_window(monkeypatch):
    monkeypatch.setattr(wu, "list_windows", lambda: [(6, "A", "c", 0, 0, 900, 900)])
    monkeypatch.setattr(wu, "foreground_top_window", lambda: None)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "chrome.exe")
    monkeypatch.setattr(wu, "find_window", lambda process: "FALLBACK")
    wu._REMEMBERED.hwnd = 5                      # 不在可见集合里

    assert wu.game_window("chrome.exe") == "FALLBACK"


def test_game_window_survives_window_enumeration_error(monkeypatch):
    monkeypatch.setattr(wu, "list_windows",
                        lambda: (_ for _ in ()).throw(RuntimeError("枚举失败")))
    monkeypatch.setattr(wu, "foreground_top_window", lambda: 8)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "chrome.exe")
    wu._REMEMBERED.hwnd = None

    # 枚举失败也要能用前台那扇（不然一崩就完全抓不到图）
    assert wu.game_window("chrome.exe") == 8


def test_game_window_skips_foreground_from_other_process(monkeypatch):
    monkeypatch.setattr(wu, "list_windows", lambda: [(1, "A", "c", 0, 0, 900, 900)])
    monkeypatch.setattr(wu, "foreground_top_window", lambda: 1)
    monkeypatch.setattr(wu, "process_name", lambda hwnd: "notepad.exe")
    monkeypatch.setattr(wu, "find_window", lambda process: "FALLBACK")
    wu._REMEMBERED.hwnd = None

    assert wu.game_window("chrome.exe") == "FALLBACK"


def test_window_title_error_is_empty(monkeypatch):
    monkeypatch.setattr(wu, "find_window", lambda p: 5)
    monkeypatch.setattr(wu.win32gui, "GetWindowText",
                        lambda hwnd: (_ for _ in ()).throw(RuntimeError("没了")))
    assert wu.window_title("game.exe") == ""
