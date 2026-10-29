"""cProfile 抓「首次 QML 实例化」期间的 Python 调用，看 1.8 秒里有没有 Python 的份。

跑：python tools/profile_qml_create.py
"""

import cProfile
import io
import os
import pstats
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["CHAITA_NO_UI_STATE"] = "1"

from PySide6.QtCore import QUrl, QTimer                    # noqa: E402
from PySide6.QtGui import QGuiApplication                   # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow                    # noqa: E402,F401

app = QGuiApplication(sys.argv[:1])
from chaita.ui import main as ov                         # noqa: E402

engine = QQmlApplicationEngine()
controller = ov.Controller()
engine.rootContext().setContextProperty("controller", controller)
comp = QQmlComponent(engine)
comp.loadUrl(ov.qml_url())

profiler = cProfile.Profile()
t0 = time.perf_counter()
profiler.enable()
obj = comp.create()
profiler.disable()
t1 = time.perf_counter()
print("create() 总共 %.0f ms（其中 Python 侧见下）" % ((t1 - t0) * 1000))
stream = io.StringIO()
stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
stats.print_stats(25)
text = stream.getvalue()
print("\n".join(text.splitlines()[:40]))

QTimer.singleShot(0, app.quit)
app.exec()
