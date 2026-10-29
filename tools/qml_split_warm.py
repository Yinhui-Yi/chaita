"""把 QML 加载拆成「编译」和「实例化」两段，各量 3 轮（第 2 轮起是热的）。"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QUrl, QTimer                      # noqa: E402
from PySide6.QtGui import QGuiApplication                    # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow                     # noqa: E402,F401

app = QGuiApplication(sys.argv[:1])
from chaita.ui import main as ov                          # noqa: E402

controller = ov.Controller()
print("QML 行数：%d" % (ov.OVERLAY_QML.count("\n") + 1))

for round_no in range(3):
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    comp = QQmlComponent(engine)
    t0 = time.perf_counter()
    comp.loadUrl(ov.qml_url())
    t1 = time.perf_counter()
    obj = comp.create() if comp.isReady() else None
    t2 = time.perf_counter()
    print("第 %d 轮  编译 %6.0f ms  实例化 %6.0f ms  小计 %6.0f ms  %s"
          % (round_no + 1, (t1 - t0) * 1000, (t2 - t1) * 1000, (t2 - t0) * 1000,
             "OK" if obj is not None else "失败"), flush=True)

QTimer.singleShot(0, app.quit)
app.exec()
