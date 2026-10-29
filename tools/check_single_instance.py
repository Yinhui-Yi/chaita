"""复现/回归：连开两次 `run.py`，会不会出现两个悬浮层。

以前「已知限制」里写着"单实例保护未做：连点两次会开两个悬浮层"。这支脚本
真开两个进程、数一下标题叫 ChaitaAssistant 的可见窗口有几个，然后都关掉。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\check_single_instance.py
"""

import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def overlay_windows(pids):
    import win32gui
    import win32process

    found = []

    def callback(hwnd, _):
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return
        if pid in pids and win32gui.IsWindowVisible(hwnd):
            found.append((hwnd, pid, win32gui.GetWindowText(hwnd),
                          win32gui.GetClassName(hwnd)))

    win32gui.EnumWindows(callback, None)
    return [item for item in found if "QWindowTool" in item[3]]


def launch():
    return subprocess.Popen([PY, "run.py"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")


def main() -> int:
    import win32con
    import win32gui

    first = launch()
    time.sleep(3.0)
    second = launch()
    time.sleep(6.0)

    alive = {proc.pid for proc in (first, second) if proc.poll() is None}
    windows = overlay_windows(alive)
    print("第一个进程 pid=%s，第二个 pid=%s" % (first.pid, second.pid))
    print("活着的进程：", sorted(alive))
    print("悬浮层窗口数：", len(windows))
    for hwnd, pid, title, cls in windows:
        print("   ", hwnd, pid, repr(title), cls)

    for hwnd, _, _, _ in windows:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    for proc in (first, second):
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("退出码：", first.returncode, second.returncode)
    return 0 if len(windows) == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
