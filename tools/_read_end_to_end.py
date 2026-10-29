"""跑一次真的「读取」全链路（不碰游戏窗口）：拿存盘的地图截图走 read.read。

验的是**多会话**这条路：判画面类型 → 地图一个会话三问 → 状态一问 → 额外字段一问。
2026-10-26 之前这里第二问就报 `Event loop is closed`（见 docs/REDESIGN_NOTES.md 第 10 节）。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\_read_end_to_end.py
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402

from chaita.game import read as game_read                 # noqa: E402
from chaita.game import towers                            # noqa: E402

SAMPLE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "chaita",
                      "20261025234046_map_h5_3.png")


def main() -> int:
    image = cv2.imread(SAMPLE)
    if image is None:
        print("读不到样图:", SAMPLE)
        return 1
    tower = towers.TOWERS["h5"]
    print("样图 %dx%d，塔 %s" % (image.shape[1], image.shape[0], tower.name))
    started = time.time()
    result = game_read.read(tower, image=image, screen="map")
    print("读取全链路 %.1f s" % (time.time() - started))
    print("kind:", result.kind, " floor:", (result.status or {}).get("floor"))
    print("mons:", [row.get("name") for row in (result.monsters or [])])
    print("items:", [row.get("name") for row in (result.items or [])])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
