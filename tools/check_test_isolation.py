"""查"测试文件在 import 阶段改环境变量"这类污染。

为什么单开一支：`tests/test_zz_isolation.py` 是在**所有测试模块都 import 完**
之后才快照的，抓不到 import 阶段的污染 —— 而踩过的那次正是这种：
`tests/test_startup.py` 顶部一句 `os.environ.setdefault("QT_QPA_PLATFORM",
"offscreen")`，整个进程都变成 offscreen，`test_worker` 直接卡了三分钟。

做法：起两个干净子进程，只 import 产品包（基线） vs 再 import 全部测试模块，
把两次看到的环境变量比一下 —— 差出来的就是测试自己的污染。
（`chaita/ui/__init__.py` 会设 `QT_PLUGIN_PATH` 这类东西，那是产品行为，两份都有，
不会误报。）

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\check_test_isolation.py
"""

import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")

WATCH_PREFIX = ("CHAITA_", "QT_")
WATCH_EXACT = ("U2NET_HOME",)

CHILD = r'''
import glob, json, os, sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {tests!r})
import chaita.ui.main  # noqa: F401  （产品包：会按设计设 QT_* 路径）
if {with_tests}:
    for path in sorted(glob.glob(os.path.join({tests!r}, "test_*.py"))):
        __import__(os.path.basename(path)[:-3])
print("ENV" + json.dumps({{k: v for k, v in os.environ.items()}}))
'''


def snapshot(with_tests: bool) -> dict:
    script = CHILD.format(root=ROOT, tests=TESTS, with_tests=with_tests)
    result = subprocess.run([sys.executable, "-c", script],
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    lines = [line for line in result.stdout.splitlines() if line.startswith("ENV")]
    if not lines:
        raise RuntimeError(result.stdout[-2000:])
    return json.loads(lines[-1][3:])


def watched(env: dict) -> dict:
    return {key: value for key, value in env.items()
            if key.startswith(WATCH_PREFIX) or key in WATCH_EXACT}


def main() -> int:
    try:
        baseline = watched(snapshot(with_tests=False))
        polluted = watched(snapshot(with_tests=True))
    except RuntimeError as exc:
        print("子进程跑挂了：")
        print(exc)
        return 1

    keys = set(baseline) | set(polluted)
    changed = {key: (baseline.get(key), polluted.get(key))
               for key in keys if baseline.get(key) != polluted.get(key)}
    print("对比了 %d 个环境变量（基线=只 import 产品包）" % len(keys))
    if not changed:
        print("OK：测试模块 import 没有额外改动环境变量")
        return 0
    for key, (old, new) in sorted(changed.items()):
        print("!! %s: %r → %r" % (key, old, new))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
