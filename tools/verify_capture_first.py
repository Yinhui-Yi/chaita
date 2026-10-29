"""证明：截图路径不再 import AI（read 模块），并量一下各自的耗时。"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["CHAITA_NO_UI_STATE"] = "1"

from PySide6.QtGui import QGuiApplication                 # noqa: E402

app = QGuiApplication(sys.argv[:1])

from chaita.game import capture as capture_mod            # noqa: E402
from chaita.game import towers                            # noqa: E402
from chaita.ui import main as ov                       # noqa: E402

print("import overlay 之后，read 在不在 sys.modules：",
      "chaita.game.read" in sys.modules)

controller = ov.Controller()
controller._post = lambda call: call()
controller._tasks = [{"id": 1, "state": "running", "text": "读取中…"}]
controller._last_foreground = towers.H5_MOTA.process

started = time.perf_counter()
target, image = controller._capture(1, 1, None, towers, capture_mod)
elapsed = (time.perf_counter() - started) * 1000

print("截图耗时 %.0f ms；target=%s；image=%s"
      % (elapsed,
         getattr(target, "name", None),
         None if image is None else list(image.shape)))
print("截图之后，read 在不在 sys.modules：", "chaita.game.read" in sys.modules)
print("任务上有没有缩略图：", bool(controller._tasks[0].get("url")))

started = time.perf_counter()
from chaita.game import read as _read                     # noqa: F401,E402
print("AI 链 import 耗时 %.0f ms（这一步现在排在截图之后）"
      % ((time.perf_counter() - started) * 1000))
