"""给 owner 做"地图三问要不要 look"的决策数据：同一张地图截图，两种问法各跑一遍。

对照组（现在）：三问允许 look（提示词写"最多 3 次"），实测 51-78 s、7 次左右 look。
实验组：三问都明确禁止 look，看不清就写 ???。

比的不是"谁更准"的绝对值（那张图没人工核对过），而是：
  时间、怪/资源的**条数和名字**是否和对照组一致。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\compare_look_map.py
"""

import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402

from chaita.game.agent.map import read as agent_map       # noqa: E402

SAMPLE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "chaita",
                      "20261025234046_map_h5_3.png")
NO_LOOK = ("\n\n【硬限制】不要调用 look，直接按你看到的回答；"
           "看不清的写 ??? 或留空，不要为了看清去放大。")


def main() -> int:
    image = cv2.imread(SAMPLE)
    if image is None:
        print("读不到样图:", SAMPLE)
        return 1
    print("样图 %dx%d\n" % (image.shape[1], image.shape[0]))

    runs = {
        "C 现在（允许 look，最多 3 次）": False,
        "A 三问都禁止 look": True,
    }
    saved = (agent_map.FLOOR_QUESTION, agent_map.MONSTER_QUESTION,
             agent_map.ITEM_QUESTION)
    for label, forbid in runs.items():
        if forbid:
            agent_map.FLOOR_QUESTION = saved[0] + NO_LOOK
            agent_map.MONSTER_QUESTION = saved[1] + NO_LOOK
            agent_map.ITEM_QUESTION = saved[2] + NO_LOOK
        else:
            (agent_map.FLOOR_QUESTION, agent_map.MONSTER_QUESTION,
             agent_map.ITEM_QUESTION) = saved
        started = time.time()
        data = agent_map.read(image)
        seconds = time.time() - started
        print("%-30s %5.1f s  floor=%r  怪 %d 条  资源 %d 条"
              % (label, seconds, data.get("floor"), len(data.get("mons") or []),
                 len(data.get("items") or [])))
        print("    怪：%s" % json.dumps(data.get("mons"), ensure_ascii=False))
        print("    资源：%s" % json.dumps(data.get("items"),
                                         ensure_ascii=False))
        print()
    (agent_map.FLOOR_QUESTION, agent_map.MONSTER_QUESTION,
     agent_map.ITEM_QUESTION) = saved
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
