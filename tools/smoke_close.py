"""起一次真程序，优雅关掉，报退出码 + 崩溃日志状态。

用法：python tools/smoke_close.py [等待秒数] [--software]

它按 **子进程 PID** 找窗口（标题可能变，别按标题猜），窗口拿到后发 WM_CLOSE
（等价于点 ×，走 Qt 的正常退出路径），然后等进程自己结束。
"""

import os
import subprocess
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
args = [a for a in sys.argv[1:] if not a.startswith("--")]
WAIT = float(args[0]) if args else 8.0
SOFTWARE = "--software" in sys.argv


def main() -> int:
    import win32con
    import win32gui
    import win32process

    env = dict(os.environ)
    if SOFTWARE:
        env["CHAITA_RENDER"] = "software"
    # 用户可能正开着一个悬浮层：自检再起一个的话会被单实例锁挡掉
    # （表现成"没等到主窗口"）。这个开关只给自检用。
    env["CHAITA_SKIP_SINGLE_INSTANCE"] = "1"

    proc = subprocess.Popen([PY, "run.py"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    # 冷启动 + 首次加载 QML 可能要好几秒：轮询等窗口出现，别一次查不到就判死
    hwnd = None
    deadline = time.time() + max(WAIT, 20.0)
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        hwnds = []

        def cb(h, _):
            try:
                _, pid = win32process.GetWindowThreadProcessId(h)
            except Exception:
                return
            if pid == proc.pid and win32gui.IsWindowVisible(h):
                hwnds.append((h, win32gui.GetWindowText(h),
                              win32gui.GetClassName(h)))

        win32gui.EnumWindows(cb, None)
        targets = [h for h, _, cls in hwnds if "QWindowTool" in cls]
        if targets:
            print("窗口:", hwnds)
            hwnd = targets[0]
            break
        time.sleep(0.5)

    if hwnd is None:
        try:
            proc.kill()
        except Exception:
            pass
        out, err = proc.communicate()
        print("没等到主窗口；退出码", proc.returncode)
        for line in [x for x in (err or "").splitlines() if x.strip()][-5:]:
            print("   ", line)
        return 1
    time.sleep(WAIT)   # 让窗口真正画出来再关
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    try:
        out, err = proc.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        print("!! 25 秒没退出，强杀")
        return 1

    print("退出码:", proc.returncode)
    err_lines = [line for line in (err or "").splitlines() if line.strip()]
    print("stderr 行数:", len(err_lines), "（收尾噪音，0 最好）")
    for line in err_lines[-4:]:
        print("   ", line)
    crash = os.path.join(ROOT, "logs", "crash.log")
    size = os.path.getsize(crash) if os.path.exists(crash) else -1
    print("logs/crash.log 大小:", size, "（0 = 这次没崩）")
    ok = proc.returncode == 0 and size == 0
    print("结果:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
