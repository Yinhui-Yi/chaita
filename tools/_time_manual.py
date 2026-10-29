"""量一次「读怪物」到底多久：拿仓库里存的全尺寸手册截图跑，不碰游戏窗口。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\_time_manual.py

输入是 docs/capture/_manual_repro.png（2582×1390，通天塔1 手册页，5 只怪）。
输出：总耗时 + 每行字段 + look/sprite 次数（这些都在 logs/chaita.log 里）。
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402

from chaita.game.agent.monster import read as monster_read  # noqa: E402

SAMPLE = os.path.join(ROOT, "docs", "capture", "_manual_repro.png")


def main() -> int:
    image = cv2.imread(SAMPLE)
    if image is None:
        print("读不到样图:", SAMPLE)
        return 1
    print("样图 %dx%d" % (image.shape[1], image.shape[0]))
    started = time.time()
    rows = monster_read.read(image)
    seconds = time.time() - started
    print("读怪物 %.1f s，%d 行" % (seconds, len(rows)))
    for row in rows:
        print("  %-8s 生命 %-6s 攻击 %-5s 防御 %-5s 经验 %-4s 技能 %-10s 图 %s"
              % (row.get("name"), row.get("hp"), row.get("atk"),
                 row.get("def"), row.get("exp"), row.get("skills") or "-",
                 "有" if row.get("icon") is not None else "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
