"""改版前 / 现在 的启动时间对照（同一个入口流程，各自一个进程）。

跑：python tools/startup_regression.py old|new
两个版本都要单独进程：启动成本里有一大块是"进程内第一次实例化"，混在
一起量会把第二次量成 50 ms，没有意义。

对照用的老版本快照直接取 logs/ 里的备份（不复制进包里）：
  old = logs/overlay_before_move.py   改版前（2308 行 QML）
  mid = logs/overlay_before_sticky.py 改版中（4688 行）
"""

import importlib.util
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = ROOT
sys.path.insert(0, ROOT)
os.environ["CHAITA_NO_UI_STATE"] = "1"

SNAPSHOTS = {
    "old": os.path.join(ROOT, "logs", "overlay_before_move.py"),
    "mid": os.path.join(ROOT, "logs", "overlay_before_sticky.py"),
}

T0 = time.perf_counter()

from PySide6.QtCore import QTimer, QUrl          # noqa: E402
from PySide6.QtGui import QGuiApplication        # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow         # noqa: E402,F401

mode = (sys.argv[1] if len(sys.argv) > 1 else "new").strip()
app = QGuiApplication(sys.argv[:1])
app.setApplicationName("ChaitaAssistant")

if mode == "new":
    from chaita.ui import main as mod
else:
    import chaita.ui  # noqa: F401  先让包存在，相对 import 才能解析
    spec = importlib.util.spec_from_file_location(
        "chaita.ui._startup_snapshot_%s" % mode, SNAPSHOTS[mode])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

controller = mod.Controller()
t_import = time.perf_counter()

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("controller", controller)
t0 = time.perf_counter()
mod.load_into(engine)
t1 = time.perf_counter()
roots = engine.rootObjects()
if not roots:
    print("%s: 加载失败" % mode)
    raise SystemExit(1)
window = roots[0]
for name, value in (("appTitle", getattr(mod, "APP_TITLE", "")),
                    ("heroIcon", getattr(mod, "HERO_ICON", "")),
                    ("iconBase", getattr(mod, "ICON_BASE", "")),
                    ("itemBase", getattr(mod, "ITEM_BASE", ""))):
    window.setProperty(name, value)
try:
    if not mod._apply_ui_state(window):
        mod._place_right(window)
except Exception:
    pass
window.setProperty("collapsed", False)
window.show()


def on_swap():
    t2 = time.perf_counter()
    print("%-4s %5d 行  进程→import完 %4.0f ms  loadData %5.0f ms  到首帧 %5.0f ms"
          % (mode, mod.OVERLAY_QML.count("\n") + 1, (t_import - T0) * 1000,
             (t1 - t0) * 1000, (t2 - t0) * 1000), flush=True)
    QTimer.singleShot(0, app.quit)


window.frameSwapped.connect(on_swap)
QTimer.singleShot(20000, app.quit)
app.exec()
