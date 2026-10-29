"""Windows 窗口查找。

按进程名匹配，不按标题：标题会随页面/文档变化，而且实测 Edge 标题里夹着
零宽字符（U+200B），按前缀匹配会莫名失败。进程名稳定得多。
"""

import os

from dataclasses import dataclass

import win32api
import win32gui
import win32process

# 只考虑够大的顶层窗口，避免抓到浮动小窗
MIN_WIDTH = 150
MIN_HEIGHT = 150


def list_windows():
    """列出可见的顶层窗口。返回 [(hwnd, 标题, 类名, 左, 上, 右, 下), ...]"""
    result = []

    def collect(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return True
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception:
            return True
        if right - left < MIN_WIDTH or bottom - top < MIN_HEIGHT:
            return True
        result.append((hwnd, title, win32gui.GetClassName(hwnd),
                       left, top, right, bottom))
        return True

    win32gui.EnumWindows(collect, None)
    return result


def foreground_top_window():
    """取当前前台窗口所属的顶层窗口句柄。

    两个游戏同时开着时，靠这个判断"用户现在在看哪个"，否则只能按固定顺序
    挨个试，先命中的那个会一直赢 —— 实测就是这样永远读到同一座塔。
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
    except Exception:
        return None
    if not hwnd:
        return None
    try:
        # 前台窗口可能是子控件，往上找到顶层
        return win32gui.GetAncestor(hwnd, 2)  # GA_ROOT
    except Exception:
        return hwnd


def process_name(hwnd: int) -> str:
    """取窗口所属进程的可执行文件名（小写）。取不到返回空串。"""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        path = win32process.GetModuleFileNameEx(handle, 0)
        return os.path.basename(path).lower()
    except Exception:
        return ""


def find_window(process: str):
    """按进程名找最大的那个可见窗口，返回 hwnd；找不到返回 None。"""
    process = process.lower()
    best = None
    for hwnd, _title, _cls, left, top, right, bottom in list_windows():
        if process not in process_name(hwnd):
            continue
        area = (right - left) * (bottom - top)
        if best is None or area > best[0]:
            best = (area, hwnd)
    return best[1] if best else None


@dataclass
class _Remembered:
    hwnd: int = None


_REMEMBERED = _Remembered()


def remember_foreground(hwnd) -> None:
    """记下"用户刚才在看的那扇窗"（悬浮层自己不算）。

    点我们自己的按钮时前台已经变成悬浮层了，所以只能靠前面采样到的这扇窗
    判断"他刚才在看哪个游戏窗口"。
    """
    if hwnd:
        _REMEMBERED.hwnd = hwnd


def game_window(process: str):
    """抓图该抓哪个窗口：**用户刚才在看的那个**，其次这个进程里最大的那个。

    浏览器里两个页面是两个窗口、进程都是 msedge.exe：只按进程挑"最大的那个"，
    用户看着 A 游戏点读取，可能抓到 B 页面 —— 读回来的怪物名会来自另一座塔
    （实测见过把另一座经典样板塔的「绿头怪/红头怪」读进来）。

    顺序：前台窗口（现在正在看的）→ 记下来的那个（点我们悬浮层之前在看的那扇，
    见 `remember_foreground`）→ 同进程里最大的。只认看得见的窗口，别抓死句柄。
    """
    wanted = (process or "").lower()
    if not wanted:
        return None
    try:
        visible = {row[0] for row in list_windows()}
    except Exception:
        visible = set()
    for hwnd in (foreground_top_window(), _REMEMBERED.hwnd):
        if hwnd and (not visible or hwnd in visible) \
                and wanted in process_name(hwnd):
            return hwnd
    return find_window(process)


def window_title(process: str) -> str:
    """取窗口标题，找不到返回空串。"""
    hwnd = find_window(process)
    if hwnd is None:
        return ""
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return ""


# 浏览器标题里这些片段属于外壳，不属于塔名
_BROWSER_NOISE = (
    "和另外", "个页面", "Microsoft", "Google Chrome", "HTML5魔塔",
    "HTML5 魔塔", "Edge", "工作", "个人",
)


def clean_title(title: str) -> str:
    """从窗口标题里取出塔名。

    实测：
      RM 教程塔        -> "教程塔"
      Edge 里的 h5 塔  -> "坐牢成仙 - HTML5魔塔 和另外 14 个页面 - 工作 - Microsoft Edge"
                          -> "坐牢成仙"
    """
    if not title:
        return ""
    head = title.split(" - ")[0].strip()
    for noise in _BROWSER_NOISE:
        if noise in head:
            head = head.split(noise)[0].strip(" -")
    # 标题里可能夹零宽字符（实测 Edge 有 U+200B）
    head = "".join(ch for ch in head if ch.isprintable() and ch != "\u200b")
    return head.strip()
