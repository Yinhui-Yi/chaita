"""验证：顶栏「读取」按钮点第 2、3 次还能不能触发。

用真实 QML 界面 + 假读取（每次 2 秒），模拟连续点击，打印 active/reading 变化。
"""

import os
import sys
import time

import numpy as np
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import chaita.game.read as G          # noqa: E402
import chaita.ui.main as O         # noqa: E402
from chaita.game.read import Reading  # noqa: E402


def main():
    app = QGuiApplication(sys.argv[:1])
    G.grab_window = lambda p: np.zeros((40, 40, 3), np.uint8)
    G.map_snapshot = lambda t, img: np.zeros((10, 10, 3), np.uint8)
    G.classify = lambda img, api_key=None: "map"

    def slow(tower, api_key=None, image=None, screen=None):
        time.sleep(2)
        return Reading(status={"floor": "第1层", "hp": 1},
                       map=np.zeros((5, 5, 3), np.uint8), name="t")

    G.read = slow

    controller = O.Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    O.load_into(engine)
    window = engine.rootObjects()[0]
    controller.attach(window)
    window.setProperty("collapsed", False)
    window.setProperty("width", 340)
    window.setProperty("height", 700)
    window.show()

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    pump(0.5)

    button = None
    for obj in window.findChildren(QObject):
        try:
            if obj.property("implicitWidth") == 54 and obj.property("implicitHeight") == 22:
                button = obj
                break
        except Exception:
            pass
    print("BUTTON_FOUND", button is not None, flush=True)
    if button is None:
        return 1

    def scene_pos(item):
        """沿 QML 的 parent 链累加坐标。findChildren 拿到的是 QObject，
        没有 width()/x() 这些方法，只能读属性。"""
        x = y = 0.0
        node = item
        for _ in range(20):
            try:
                x += float(node.property("x") or 0)
                y += float(node.property("y") or 0)
                node = node.property("parent")
            except Exception:
                break
            if node is None:
                break
        return x, y

    sx, sy = scene_pos(button)
    size = (float(button.property("width") or 0), float(button.property("height") or 0))
    print("BUTTON_AT", round(sx), round(sy), size, flush=True)
    point = QPoint(int(sx + size[0] / 2), int(sy + size[1] / 2))

    for index in range(3):
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        pump(0.25)
        print("CLICK", index + 1, "active=", controller._active,
              "reading=", controller._reading, flush=True)

    pump(2.6)
    print("END active=", controller._active, "reading=", controller._reading,
          "entries=", len(controller._map_history), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
