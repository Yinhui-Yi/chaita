"""量一次"对话坞长出来"到底顺不顺：数动画期间的帧。

为什么要有它：owner 说"过渡不流畅"，光看截帧看不出掉帧 —— 要的是**帧间隔**。
这里直接接 `QQuickWindow.frameSwapped`，在动画那 400ms 里数有多少帧、
最大间隔是多少（>25ms 就是肉眼能看出来的卡）。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\check_fps.py
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer, QUrl                    # noqa: E402
from PySide6.QtGui import QGuiApplication                  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine            # noqa: E402

from chaita.ui import main as ov                        # noqa: E402

WINDOW_W, WINDOW_H = 340, 700


def main() -> int:
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("ChaitaAssistant")
    controller = ov.Controller()
    controller._last_status = {"hp": 1200, "atk": 15}
    controller._apply_status(controller._last_status)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    ov.load_into(engine)
    if not engine.rootObjects():
        print("QML 没加载起来")
        return 1
    window = engine.rootObjects()[0]
    window.setProperty("width", WINDOW_W)
    window.setProperty("height", WINDOW_H)
    window.setProperty("savedWidth", WINDOW_W)
    window.setProperty("savedHeight", WINDOW_H)
    window.show()

    stamps = []

    def on_swapped():
        stamps.append(__import__("time").monotonic())

    window.frameSwapped.connect(on_swapped)

    what = sys.argv[1] if len(sys.argv) > 1 else "grow"

    def grow():
        stamps.clear()
        if what == "collapse":
            # 折叠：窗口高度由 Python 逐帧改（Controller.animateSize 180ms）
            controller.animateSize(WINDOW_W, 56, 180)
            return
        controller._chat_log = [
            {"who": "你", "text": "这层还有几只怪？"},
            {"who": "AI", "text": "我记着 4 只：监狱守卫 ×6、血蚁 ×3、铁卫 ×1。"},
        ]
        controller.chatLogChanged.emit()

    def report():
        if len(stamps) < 2:
            print("没抓到帧（窗口没在渲染？）")
            app.quit()
            return
        gaps = [(stamps[i + 1] - stamps[i]) * 1000
                for i in range(len(stamps) - 1)]
        gaps.sort()
        span = (stamps[-1] - stamps[0]) * 1000
        print("动画期间帧数 %d，跨度 %.0f ms" % (len(stamps), span))
        print("帧间隔：中位 %.1f ms，最大 %.1f ms，>25ms 的 %d 帧"
              % (gaps[len(gaps) // 2], gaps[-1],
                 len([g for g in gaps if g > 25])))
        app.quit()

    # 先让首帧画出来（实测要 ~1.2 s）
    QTimer.singleShot(1400, grow)
    QTimer.singleShot(2000, report)
    QTimer.singleShot(9000, app.quit)
    code = app.exec()
    del engine
    return code


if __name__ == "__main__":
    raise SystemExit(main())
