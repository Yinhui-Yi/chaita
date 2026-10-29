"""截图（从 read.py 拆出来，故意**不 import** 任何 AI 模块）。

为什么单独一个模块：点「读怪物」「读地图」时要**立刻**截图，而 read.py 会把整条
AI 链（agent_framework → openai）拖进来、要 1.5-2 秒。截图先落袋，AI 的 import 放
后面，模型看到的才会是"点下去那一刻"的画面。
"""

import ctypes

import cv2
import numpy as np


def grab(process: str):
    """抓窗口画面（PrintWindow：窗口被盖住也能抓到）。

    抓的是**用户正在看的那个窗口**（`winutil.game_window`：前台优先、否则最大的），
    不是"这个进程里最大的那个" —— 浏览器两个页面是两个窗口、进程一样，
    按"最大"挑会抓到另一个页面，读回来的怪物名就来自另一座塔。

    拿到的是逻辑像素（150% 缩放下比屏幕像素小）；这里只给人看和给模型看，
    不需要跟屏幕像素对齐。
    """
    ctypes.windll.user32.SetProcessDPIAware()
    import win32gui
    import win32ui

    from . import winutil

    hwnd = winutil.game_window(process)
    if hwnd is None:
        return None

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    window_dc = win32gui.GetWindowDC(hwnd)
    src_dc = win32ui.CreateDCFromHandle(window_dc)
    mem_dc = src_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(src_dc, width, height)
    mem_dc.SelectObject(bitmap)
    # flag=2 = PW_RENDERFULLCONTENT：浏览器等 GPU 合成的窗口必须用它
    ctypes.windll.user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 2)
    raw = bitmap.GetBitmapBits(True)
    image = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
    image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    win32gui.DeleteObject(bitmap.GetHandle())
    mem_dc.DeleteDC()
    src_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, window_dc)
    return image


def find_target(towers, foreground: str):
    """点读取时该读哪座塔：优先"刚才在前台的那个"，否则只在开着唯一一个时兜底。

    不按固定顺序挨个试：两座塔都开着时，先命中的永远赢，用户看着 A 点读取
    却读到 B，看起来就是"点了没用"。
    """
    if foreground:
        for tower in towers.values():
            if tower.process == foreground:
                return tower
    from . import winutil
    running = []
    for tower in towers.values():
        try:
            if winutil.find_window(tower.process):
                running.append(tower)
        except Exception:
            continue
    return running[0] if len(running) == 1 else None


def describe_failure(towers, foreground: str) -> str:
    """找不到目标时给人看的那句话（说清前台是谁、开了几个）。"""
    from . import winutil
    running = []
    for tower in towers.values():
        try:
            if winutil.find_window(tower.process):
                running.append(tower)
        except Exception:
            continue
    what = foreground or "（没采样到）"
    detail = "刚才在前台的是：%s\n请把游戏窗口切到前台，再点「读取」。" % what
    if len(running) > 1:
        detail += "\n同时开着 %d 个游戏窗口，没法判断该读哪个。" % len(running)
    return detail
