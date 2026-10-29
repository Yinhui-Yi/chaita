"""验证：点顶栏（不是按钮）时，只有标题区会折叠，按钮右侧不该折叠。

之前的行为：瞄着「读取」点偏 1~2 像素 → 落在顶栏 → 窗口折叠 → 按钮消失，
用户看到的就是"读取按不了"。
"""

import os
import sys
import time

import numpy as np
from PySide6.QtCore import QObject, QPoint, Qt, QUrl
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
    G.read = lambda tower, api_key=None, image=None, screen=None: Reading(
        status={"floor": "第1层", "hp": 1}, map=np.zeros((5, 5, 3), np.uint8),
        name="t")

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

    def click(x, y):
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(x, y))
        pump(0.25)

    print("初始 collapsed =", window.property("collapsed"), flush=True)

    # 1) 点按钮右边一点（原来会折叠的地方）
    click(140, 22)
    print("点按钮右侧 -> collapsed =", window.property("collapsed"), flush=True)

    # 2) 点更右边（塔名附近）
    click(300, 22)
    print("点塔名附近 -> collapsed =", window.property("collapsed"), flush=True)

    # 3) 点标题区 -> 应该折叠
    click(40, 22)
    print("点标题区 -> collapsed =", window.property("collapsed"), flush=True)

    # 4) 折叠状态下点标题区 -> 应该展开
    click(40, 22)
    print("折叠后点标题区 -> collapsed =", window.property("collapsed"), flush=True)

    # 5) 再折叠一次，然后点右侧看能不能展开
    if not window.property("collapsed"):
        click(40, 22)
    print("准备再折叠 -> collapsed =", window.property("collapsed"),
          "height =", window.property("height"), flush=True)
    click(300, 22)
    print("折叠后点右侧 -> collapsed =", window.property("collapsed"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
