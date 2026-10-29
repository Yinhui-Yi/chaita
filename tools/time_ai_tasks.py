"""量真实耗时：抓一帧 → 判画面 → 读地图（一个会话）/ 读怪物（关思考）。

⚠ **会抓你的游戏窗口**（`capture.grab`，走 PrintWindow，不动窗口本身但会去读它的画面）。
owner 说过「别动我游戏」，所以**默认不要跑**；要量耗时请用这两支（只读磁盘上的截图）：

    tools/_time_manual.py       量「读怪物」
    tools/_read_end_to_end.py   量「读取」全链路

下面这支只在 owner 明确同意、且桌面确实停在手册页/地图页时才用：
跑的时候读到什么取决于屏幕上现在是什么页面，这里只量耗时，不看结果对不对。
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["CHAITA_NO_UI_STATE"] = "1"

if not os.environ.get("CHAITA_ALLOW_GRAB"):
    raise SystemExit("这是要抓游戏窗口的工具。确认要跑就先设 CHAITA_ALLOW_GRAB=1"
                     "（或改用 tools/_time_manual.py / tools/_read_end_to_end.py）")

from chaita import config                                  # noqa: E402
from chaita.game import capture                             # noqa: E402
from chaita.game import towers                              # noqa: E402

key = config.api_key()
image = capture.grab(towers.H5_MOTA.process)
if image is None:
    raise SystemExit("抓不到游戏窗口")
print("抓到的画面", image.shape)

from chaita.game.agent import map as agent_map              # noqa: E402
from chaita.game.agent import monster as agent_monster      # noqa: E402

started = time.time()
screen = agent_map.classify(image, api_key=key)
print("判画面：%r  耗时 %.1f s" % (screen, time.time() - started))

if screen == "manual":
    started = time.time()
    rows = agent_monster.read(image, api_key=key)
    print("读怪物（关思考）：%d 只  耗时 %.1f s"
          % (len(rows), time.time() - started))
else:
    started = time.time()
    result = agent_map.read(image, api_key=key)
    print("读地图（一个会话问 3 句）：层 %r，怪 %d 种，资源 %d 种  耗时 %.1f s"
          % (result["floor"], len(result["mons"]), len(result["items"]),
             time.time() - started))
