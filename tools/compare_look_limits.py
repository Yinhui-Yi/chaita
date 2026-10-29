"""给 owner 做"look 上限"的决策数据：同一张手册页，三种上限各跑一遍。

为什么要有这支：`look` 每调一次就是一次模型往返（实测每次 ~6 秒），现在提示词
对次数**没有硬上限**，于是同一次读怪物在 21-56 秒之间飘。砍 look 会更快，但可能
多出 `???` —— 这个取舍该 owner 定，不该我拍。这支脚本把三种上限的时间/条数/准确度
实测出来，供他一句话选。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\compare_look_limits.py

跑三遍真模型（不碰游戏窗口，只读 docs/capture/_manual_repro.png）。
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402

from chaita.game.agent.monster import read as monster     # noqa: E402

SAMPLE = os.path.join(ROOT, "docs", "capture", "_manual_repro.png")

# 从那张截图上人工核对过的真值：名字 → (生命, 攻击, 防御, 经验)
TRUTH = {
    "红头怪": ("80", "25", "1", "1"),
    "骷髅人": ("200", "50", "10", "1"),
    "小蝙蝠": ("100", "30", "3", "1"),
    "青头怪": ("100", "26", "3", "1"),
    "大蝙蝠": ("120", "35", "5", "1"),
}

BASE = monster.PROMPT
CAP_NOTES = {
    "C 现在（没上限）": "",
    "B 每只怪最多 1 次 sprite、整页最多 1 次 look":
        "\n\n【硬限制】整页最多调 1 次 look、每只怪最多调 1 次 sprite；"
        "还是看不清就按看到的写，看不清的数字写 ???，不要再调。",
    "A 不许 look、每只怪最多 1 次 sprite":
        "\n\n【硬限制】不要调用 look；每只怪最多调 1 次 sprite；"
        "看不清的数字写 ???。",
}


def score(rows) -> tuple:
    """(命中字段数, 总字段数, 问号数)"""
    hit = total = question = 0
    for row in rows:
        truth = TRUTH.get(row.get("name"))
        for key in ("hp", "atk", "def", "exp"):
            value = str(row.get(key) or "")
            total += 1
            if "?" in value:
                question += 1
            if truth and value == truth[("hp", "atk", "def", "exp").index(key)]:
                hit += 1
    return hit, total, question


def main() -> int:
    image = cv2.imread(SAMPLE)
    if image is None:
        print("读不到样图:", SAMPLE)
        return 1
    print("样图 %dx%d，真值 5 只怪\n" % (image.shape[1], image.shape[0]))

    for label, note in CAP_NOTES.items():
        monster.PROMPT = BASE + note
        started = time.time()
        rows = monster.read(image)
        seconds = time.time() - started
        hit, total, question = score(rows)
        names = "、".join(str(row.get("name")) for row in rows)
        print("%-46s %5.1f s  %d 行  字段命中 %d/%d  问号 %d"
              % (label, seconds, len(rows), hit, total, question))
        print("    读到：%s" % names)
    monster.PROMPT = BASE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
