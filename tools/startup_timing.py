"""量启动每一步的花销：从进程起来到第一帧真的画出来。

跑：python tools/startup_timing.py
输出每一步的累计时间和增量，外加 python -X importtime 里最慢的几个模块。
"""

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

T0 = time.perf_counter()
marks = []


def mark(name):
    now = time.perf_counter()
    marks.append((name, now - T0))


mark("进程起来")

sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer, QUrl          # noqa: E402
from PySide6.QtGui import QGuiApplication       # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow         # noqa: E402

mark("PySide6 导入")

from chaita.ui import main as ov              # noqa: E402

mark("chaita.ui.main 导入")

app = QGuiApplication(sys.argv[:1])
mark("QGuiApplication")

controller = ov.Controller()
mark("Controller()")

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("controller", controller)
ov.load_into(engine)
mark("QML 编译 + 实例化")

if not engine.rootObjects():
    print("加载失败")
    raise SystemExit(1)
window = engine.rootObjects()[0]
controller.attach(window)
window.setProperty("appTitle", ov.APP_TITLE)
window.setProperty("heroIcon", ov.HERO_ICON)
window.setProperty("iconBase", ov.ICON_BASE)
window.setProperty("itemBase", ov.ITEM_BASE)
if not ov._apply_ui_state(window):
    ov._place_right(window)
window.setProperty("collapsed", False)
controller.markGeometryReady()
window.show()
mark("show() 调用完")


def on_swap():
    mark("第一帧真的画出来")
    QTimer.singleShot(0, app.quit)


window.frameSwapped.connect(on_swap)
QTimer.singleShot(6000, app.quit)
app.exec()

print()
prev = 0.0
for name, at in marks:
    print("%-22s %7.0f ms  (+%5.0f ms)" % (name, at * 1000, (at - prev) * 1000))
    prev = at
print("%-22s %7.0f ms" % ("总计（可执行路径）", marks[-1][1] * 1000))

# 解释器 + import 的真实花销：单独测一次 -X importtime 的汇总
print()
out = subprocess.run(
    [PY, "-X", "importtime", "-c",
     "import sys; sys.path.insert(0, %r); import chaita.ui.main"
     % ROOT],
    capture_output=True, text=True)
rows = []
for line in out.stderr.splitlines():
    line = line.strip()
    if not line.startswith("import time:"):
        continue
    parts = line.split("|")
    if len(parts) < 3:
        continue
    try:
        us = int(parts[1].strip())
    except ValueError:
        continue
    rows.append((us, parts[2].strip()))
rows.sort(reverse=True)
print("importtime 最慢的 12 个模块：")
for us, name in rows[:12]:
    print("  %8.0f ms  %s" % (us / 1000.0, name))
total = subprocess.run(
    [PY, "-X", "importtime", "-c",
     "import sys; sys.path.insert(0, %r); import chaita.ui.main"
     % ROOT], capture_output=True, text=True).stderr
acc = 0
for line in total.splitlines():
    if line.strip().startswith("import time:"):
        try:
            acc += int(line.split("|")[1].strip())
        except (IndexError, ValueError):
            pass
print("  累积 import 总时间 %.0f ms" % (acc / 1000.0))
