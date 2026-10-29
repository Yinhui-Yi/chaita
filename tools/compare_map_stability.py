"""量「读地图」的名字稳不稳：同一张图跑两遍，看怪名是否一致。

为什么要量：同一张 632×632 地图截图，两次跑出过
「红史莱姆 / 红头怪」「蓝蝙蝠 / 紫蝙蝠」这种差异 —— 玩家看到的是"每次读都不一样"。
这一轮给读地图加了 known（面板里已有的怪名当候选），这支脚本负责对比
"有候选 / 没候选"两种情况下两次跑的一致程度。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\compare_map_stability.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402

from chaita.game.agent.map import read as agent_map       # noqa: E402

SAMPLE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "chaita",
                      "20261025234046_map_h5_3.png")
# 这一层曾经读出来的名字，当作"面板里已经有这些怪"的候选
HINTS = ["红史莱姆", "绿史莱姆", "紫蝙蝠", "骷髅人", "骷髅队长",
         "紫史莱姆", "紫色球怪", "红色角怪"]


def names_of(rows) -> set:
    return {str(row.get("name")) for row in (rows or [])}


def run(label, image, known) -> set:
    data = agent_map.read(image, known=known)
    got = names_of(data.get("mons"))
    print("%-22s 怪 %d 条：%s" % (label, len(got), "、".join(sorted(got))))
    return got


def main() -> int:
    image = cv2.imread(SAMPLE)
    if image is None:
        print("读不到样图:", SAMPLE)
        return 1
    print("样图 %dx%d，候选名 %d 个\n" % (image.shape[1], image.shape[0],
                                        len(HINTS)))

    print("== 没有候选名（以前的行为）==")
    first = run("第一次", image, None)
    second = run("第二次", image, None)
    print("两次一致：%d 个共同 / %d 个并集\n"
          % (len(first & second), len(first | second)))

    print("== 带候选名（这一轮加的）==")
    third = run("第一次", image, HINTS)
    fourth = run("第二次", image, HINTS)
    print("两次一致：%d 个共同 / %d 个并集"
          % (len(third & fourth), len(third | fourth)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
