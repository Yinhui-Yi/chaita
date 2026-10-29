"""测：启动后多久画面里开始有内容（排布局是否变慢）。"""

import sys

sys.path.insert(0, os.getcwd())

import numpy as np
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401

from chaita.ui import main as ov

app = QGuiApplication(sys.argv[:1])
controller = ov.Controller()
controller._map_history = [{"floor": "地下30", "url": "",
                            "mons": [{"name": "红头怪", "count": 2}],
                            "items": []}]
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("controller", controller)
ov.load_into(engine)
window = engine.rootObjects()[0]
controller.attach(window)
window.setProperty("appTitle", ov.APP_TITLE)
window.setProperty("collapsed", False)
window.setProperty("width", 340)
window.setProperty("height", 712)
window.setProperty("x", -6000)
window.setProperty("y", -6000)
window.show()
controller.mapHistoryChanged.emit()


def bright_count():
    shot = window.grabWindow()
    img = shot.convertToFormat(QImage.Format_RGBA8888)
    width, height = img.width(), img.height()
    raw = bytes(img.constBits())
    arr = np.frombuffer(raw, dtype=np.uint8)
    arr = arr.reshape(height, img.bytesPerLine() // 4, 4)[:, :width, :3]
    body = arr[180:420, 20:300]
    return int((body.max(axis=2) > 90).sum())


for delay in (300, 600, 900, 1200, 1600, 2200, 3000):
    QTimer.singleShot(delay, lambda d=delay: print("t=%dms body_bright=%d"
                                                  % (d, bright_count()), flush=True))
QTimer.singleShot(3400, app.quit)
app.exec()
