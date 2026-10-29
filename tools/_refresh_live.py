"""验一次「↻」（某层行尾那个刷新）：拿存盘地图截图走 read_floor_monsters。

它和「读地图」的区别：只要"这层有哪些怪、各几只"，不需要层号和资源；
界面上传的是那一层存下来的地图截图（`_start_scan_task` 从磁盘读），不碰游戏窗口。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\_refresh_live.py
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402

from chaita.game import read as game_read                 # noqa: E402

SAMPLE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "chaita",
                      "20261025234046_map_h5_3.png")
KNOWN = ["红史莱姆", "绿史莱姆", "骷髅人"]


def main() -> int:
    image = cv2.imread(SAMPLE)
    if image is None:
        print("读不到样图:", SAMPLE)
        return 1
    print("样图 %dx%d，已知怪 %d 只" % (image.shape[1], image.shape[0],
                                       len(KNOWN)))
    started = time.time()
    rows = game_read.read_floor_monsters(image, known=KNOWN)
    print("↻ %.1f s，%d 条" % (time.time() - started, len(rows)))
    for row in rows:
        print("  %-10s ×%s" % (row.get("name"), row.get("count")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
