"""真跑一次「读这一层有哪些怪」，量耗时 + 看结果（用你自己存的那张地图截图）。"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                              # noqa: E402
import numpy as np                                      # noqa: E402

from chaita.game import read as game_read               # noqa: E402

shot = sys.argv[1] if len(sys.argv) > 1 else (
    os.path.join(os.environ["LOCALAPPDATA"], "Temp", "chaita",
                 "20261025234046_map_h5_3.png"))
known = ["绿色史莱姆", "红色史莱姆", "小蝙蝠", "初级法师", "骷髅士兵", "黑色史莱姆"]

image = cv2.imdecode(np.fromfile(shot, dtype=np.uint8), cv2.IMREAD_COLOR)
print("截图", os.path.basename(shot), image.shape)
started = time.time()
rows = game_read.read_floor_monsters(image, known=known)
print("耗时 %.1f s" % (time.time() - started))
print("读到 %d 种：" % len(rows))
for row in rows:
    print("   %s ×%d" % (row["name"], row["count"]))
