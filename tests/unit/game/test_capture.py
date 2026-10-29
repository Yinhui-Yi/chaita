"""截图目标选择单元测试（`chaita/game/capture.py`）。

真值来自规则：前台优先、只开着唯一一个才兜底、找不到时说清开了几个。
winutil.find_window 全 stub（grab 的 PrintWindow 路径不做，属于真窗口验证）。
"""

import sys

import chaita.game.capture as cap
import chaita.game.winutil as wu
from chaita.game.towers import Tower


def _towers():
    a = Tower("a", "塔A", "a.exe")
    b = Tower("b", "塔B", "b.exe")
    return {"a": a, "b": b}


def test_find_target_prefers_foreground():
    towers = _towers()
    assert cap.find_target(towers, "a.exe") is towers["a"]


def test_find_target_unique_running(monkeypatch):
    towers = _towers()
    monkeypatch.setattr(wu, "find_window",
                        lambda p: 1 if p == "a.exe" else None)
    assert cap.find_target(towers, "") is towers["a"]


def test_find_target_ambiguous_is_none(monkeypatch):
    towers = _towers()
    monkeypatch.setattr(wu, "find_window", lambda p: 1)
    assert cap.find_target(towers, "") is None


def test_find_target_none_when_nothing(monkeypatch):
    towers = _towers()
    monkeypatch.setattr(wu, "find_window", lambda p: None)
    assert cap.find_target(towers, "") is None


def test_describe_failure_names_foreground_and_count(monkeypatch):
    towers = _towers()
    monkeypatch.setattr(wu, "find_window", lambda p: 1)
    text = cap.describe_failure(towers, "")
    assert "（没采样到）" in text
    assert "同时开着 2 个游戏窗口" in text


def test_describe_failure_single_case(monkeypatch):
    towers = _towers()
    monkeypatch.setattr(wu, "find_window", lambda p: None)
    text = cap.describe_failure(towers, "a.exe")
    assert "a.exe" in text
    assert "同时开着" not in text


# ---- 真的截图路径（PrintWindow）与"某座塔查不了"的兜底 ----

def _fake_win32(monkeypatch, rect=(0, 0, 2, 2), bits=16, keep=None):
    """把 win32 那几样换掉：只留"调用了什么"这一层语义。"""
    calls = [] if keep is None else keep

    class DC:
        def CreateCompatibleDC(self):
            return DC()

        def SelectObject(self, bitmap):
            calls.append("SelectObject")

        def GetSafeHdc(self):
            return 123

        def DeleteDC(self):
            calls.append("DeleteDC")

    class Bitmap:
        def CreateCompatibleBitmap(self, dc, width, height):
            calls.append(("CreateBitmap", width, height))

        def GetBitmapBits(self, raw):
            return bytes(bits)

        def GetHandle(self):
            return 999

    fake_gui = type("FakeGui", (), {
        "GetWindowRect": staticmethod(lambda hwnd: rect),
        "GetWindowDC": staticmethod(lambda hwnd: 777),
        "DeleteObject": staticmethod(lambda handle: calls.append("DeleteObject")),
        "ReleaseDC": staticmethod(lambda hwnd, dc: calls.append("ReleaseDC")),
    })
    fake_ui = type("FakeUi", (), {
        "CreateDCFromHandle": staticmethod(lambda dc: DC()),
        "CreateBitmap": staticmethod(lambda: Bitmap()),
    })
    user32 = type("User32", (), {
        "SetProcessDPIAware": staticmethod(lambda: 1),
        "PrintWindow": staticmethod(lambda hwnd, hdc, flag: calls.append(
            ("PrintWindow", flag)) or 1),
    })
    monkeypatch.setitem(sys.modules, "win32gui", fake_gui)
    monkeypatch.setitem(sys.modules, "win32ui", fake_ui)
    monkeypatch.setattr(cap.ctypes, "windll",
                        type("Windll", (), {"user32": user32}), raising=False)
    return calls


def test_grab_returns_bgr_image_and_cleans_up(monkeypatch):
    monkeypatch.setattr(wu, "game_window", lambda process: 42)
    calls = _fake_win32(monkeypatch)

    image = cap.grab("chrome.exe")

    assert image.shape == (2, 2, 3)          # BGRA → BGR
    assert ("PrintWindow", 2) in calls       # PW_RENDERFULLCONTENT
    # 句柄/DC 必须还回去，不然每读一次漏一个 GDI 对象
    assert "DeleteObject" in calls
    assert "ReleaseDC" in calls
    assert calls.count("DeleteDC") == 2      # src + mem 两个都删


def test_grab_returns_none_without_window(monkeypatch):
    monkeypatch.setattr(wu, "game_window", lambda process: None)
    calls = _fake_win32(monkeypatch)
    assert cap.grab("chrome.exe") is None
    assert calls == []                       # 没窗口就什么都别建


def test_find_target_skips_tower_that_cannot_be_checked(monkeypatch):
    towers = _towers()

    def find_window(process):
        if process == "a.exe":
            raise OSError("进程查不了")
        return 1

    monkeypatch.setattr(wu, "find_window", find_window)
    # a 查不了就跳过，只剩 b 开着 → 选 b
    assert cap.find_target(towers, "") is towers["b"]


def test_describe_failure_skips_tower_that_cannot_be_checked(monkeypatch):
    towers = _towers()

    def find_window(process):
        raise OSError("进程查不了")

    monkeypatch.setattr(wu, "find_window", find_window)
    text = cap.describe_failure(towers, "a.exe")
    assert "a.exe" in text
    assert "同时开着" not in text            # 一个都查不到 → 不该说"开着 2 个"
