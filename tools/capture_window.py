"""开发期采集工具：抓取目标窗口画面，供识别层量取参数用。

用 PrintWindow 让窗口自己渲染一份，因此不受被其他窗口遮挡的影响。

    python tools/capture_window.py            # 列出所有窗口
    python tools/capture_window.py rm         # 抓教程塔（标题含"教程塔"）
    python tools/capture_window.py h5         # 抓网页版（标题含"喵喵信号"）
    python tools/capture_window.py rm h5      # 两个都抓

产物写到 docs/capture/ 下，文件名带时间戳。
"""

import ctypes
import ctypes.wintypes  # noqa: F401
import os
import sys
import time

import cv2
import numpy as np
import win32api
import win32gui
import win32process
import win32ui

# 必须在任何窗口坐标调用之前声明，否则 Windows 会按 DPI 缩放虚拟化坐标，
# 拿到的矩形与实际像素不符（本机 150% 缩放下差 1.5 倍）。
ctypes.windll.user32.SetProcessDPIAware()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "capture")

# 关键字 -> 输出名。用进程名匹配（steam.exe 等改名了也不怕）。
TARGETS = {
    "rm": ("game.exe", "rm_tutorial"),
    "h5": ("msedge.exe", "h5_miaomiao"),
}


def list_windows() -> list:
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
        if right - left < 150 or bottom - top < 150:
            return True
        result.append((hwnd, title, win32gui.GetClassName(hwnd),
                       left, top, right, bottom))
        return True

    win32gui.EnumWindows(collect, None)
    return result


def process_name(hwnd: int) -> str:
    """取窗口所属进程的可执行文件名。

    比按标题匹配可靠：标题会随页面/文档变化，而且实测标题里可能夹零宽字符
    （Edge 的「喵喵信号」后面就有一个 U+200B，前缀匹配会失败）。
    """
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        path = win32process.GetModuleFileNameEx(handle, 0)
        return os.path.basename(path).lower()
    except Exception:
        return ""


def find_window(keyword: str):
    """按关键字找窗口。

    先按进程名匹配（更稳），再退回标题匹配。返回 (hwnd, 标题, 矩形)。
    """
    keyword = keyword.lower()
    best = None
    for hwnd, title, _cls, left, top, right, bottom in list_windows():
        proc = process_name(hwnd)
        # 只在顶层窗口里挑最大的那个，避免抓到小的浮动子窗口
        area = (right - left) * (bottom - top)
        if keyword in proc or keyword in title.lower():
            if best is None or area > best[0]:
                best = (area, hwnd, title, (left, top, right, bottom))
    if best is None:
        return None, None, None
    return best[1], best[2], best[3]


def grab(hwnd: int) -> np.ndarray:
    """让窗口把自身渲染到内存 DC 并取回 BGR 图。"""
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top

    window_dc = win32gui.GetWindowDC(hwnd)
    src_dc = win32ui.CreateDCFromHandle(window_dc)
    mem_dc = src_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(src_dc, width, height)
    mem_dc.SelectObject(bitmap)

    # flag=2 是 PW_RENDERFULLCONTENT，浏览器等 GPU 合成的窗口必须用这个
    ctypes.windll.user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 2)
    raw = bitmap.GetBitmapBits(True)
    image = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
    image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    win32gui.DeleteObject(bitmap.GetHandle())
    mem_dc.DeleteDC()
    src_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, window_dc)
    return image


def content_bbox(image: np.ndarray, threshold: int = 18):
    """找非黑内容的包围盒。用来排除窗口边框和游戏外的黑边。"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = gray > threshold
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


def print_windows() -> None:
    print("当前可见窗口:")
    for hwnd, title, cls, left, top, right, bottom in list_windows():
        print("  hwnd=%-10s %-14s %-46s pos(%5d,%5d) %4dx%-4d"
              % (hwnd, process_name(hwnd)[:14], title[:46], left, top,
                 right - left, bottom - top))


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tools/capture_window.py <rm|h5|list> [...]")
        print()
        print_windows()
        return 0

    if sys.argv[1] == "list":
        print_windows()
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    keys = sys.argv[1:]
    stamp = time.strftime("%H%M%S")
    for key in keys:
        if key not in TARGETS:
            print("未知目标: %s（可用: %s）" % (key, ", ".join(TARGETS)))
            continue
        keyword, name = TARGETS[key]
        hwnd, title, rect = find_window(keyword)
        if hwnd is None:
            print("%-14s 找不到标题以 %r 开头的窗口" % (name, keyword))
            continue
        image = grab(hwnd)
        left, top, right, bottom = rect
        box = content_bbox(image)
        path = os.path.join(OUT_DIR, "%s_%s.png" % (name, stamp))
        cv2.imwrite(path, image)
        print("%-14s hwnd=%-10s 窗口矩形=(%d,%d,%d,%d) %dx%d"
              % (name, hwnd, left, top, right, bottom,
                 image.shape[1], image.shape[0]))
        if box:
            print("%-14s 非黑内容区=(%d,%d,%d,%d) 尺寸 %dx%d"
                  % ("", box[0], box[1], box[2], box[3],
                     box[2] - box[0] + 1, box[3] - box[1] + 1))
        print("%-14s 已存: %s" % ("", os.path.relpath(path, ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
