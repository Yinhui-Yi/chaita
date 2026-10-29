"""反复跑界面自检，等到崩一次为止（用来复现收尾崩溃）。

    python tools/repro_synthetic_crash.py [轮数]

每轮：跑一次 tools/test_ui_synthetic.py，记录退出码 + logs/_test_crash.log 的大小。
一旦 crash log 有内容（faulthandler 写了栈）就停下，打印栈，退出码 1；
全跑完都没崩就退出码 0。
"""

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CRASH = os.path.join(ROOT, "logs", "_test_crash.log")
SYNTH = os.path.join(ROOT, "docs", "capture", "_synthetic.log")
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def size(path: str) -> int:
    """文件不存在也算 0（否则第一次跑会被误判成"涨了"）。"""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def main() -> int:
    if os.path.exists(CRASH):
        os.remove(CRASH)
    report = []
    for i in range(1, ROUNDS + 1):
        before = size(CRASH)
        started = time.time()
        proc = subprocess.run([PY, os.path.join("tools", "test_ui_synthetic.py")],
                              cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
        took = time.time() - started
        after = size(CRASH)
        tail = ""
        try:
            with open(SYNTH, encoding="utf-8") as handle:
                lines = [line.rstrip() for line in handle if line.strip()]
            tail = lines[-1] if lines else ""
        except OSError:
            tail = "(没有 _synthetic.log)"
        print("第 %d 轮: 退出码=%s 耗时=%.1fs crashlog %s→%s | %s"
              % (i, proc.returncode, took, before, after, tail), flush=True)
        report.append((i, proc.returncode, before, after, tail))
        if after > before:
            print("!! 崩了，栈如下：", flush=True)
            with open(CRASH, encoding="utf-8", errors="replace") as handle:
                print(handle.read()[-6000:], flush=True)
            return 1
        if proc.returncode not in (0,):
            print("!! 退出码异常（可能是原生崩溃，但 faulthandler 没抓到）", flush=True)
            err = (proc.stderr or "").strip().splitlines()
            print("\n".join(err[-25:]), flush=True)
            return 1
    print("跑了 %d 轮都没崩：%s" % (ROUNDS, report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
