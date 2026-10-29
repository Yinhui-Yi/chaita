"""验一次真的「对话」：拿存盘截图跑一段**多轮**对话（不碰游戏窗口）。

第三个功能（对话）以前只有桩测试；这支是**真模型往返**、只读磁盘上的截图。
它证明两件事：能聊（不是只改数字），以及记得住上一句。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\check_chat.py
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402

from chaita.game.agent.chat import reply as chat          # noqa: E402

SAMPLE = os.path.join(ROOT, "docs", "capture", "h5_miaomiao_212609.png")
STATUS = {"hp": 53, "atk": 3, "def": 2, "mdef": 4,
          "keys": {"yellow": 1, "blue": 0, "red": 0, "green": 0},
          "gold": 100, "exp": 20, "next": 20}
# 三轮：先聊天，再指正（这一轮必须改 hp），最后考它记不记得上一句
SCRIPT = ["你好，先随便聊一句", "生命不是 53，是 60", "我刚才让你把生命改成多少？"]


def main() -> int:
    image = cv2.imread(SAMPLE)
    if image is None:
        print("读不到样图:", SAMPLE)
        return 1
    print("样图 %dx%d" % (image.shape[1], image.shape[0]))
    history = []
    failures = 0
    for message in SCRIPT:
        started = time.time()
        result = chat.reply(image, STATUS, message, history=history, tries=2)
        seconds = time.time() - started
        if "_error" in result:
            print("第 %d 轮失败 %.1f s：%s"
                  % (len(history) // 2 + 1, seconds, result["_error"]))
            return 1
        said = result.get("reply") or ""
        print("你：%s" % message)
        print("AI（%.1f s）：%s" % (seconds, said[:120]))
        if result.get("status"):
            print("    顺带改了：hp=%s" % (result["status"] or {}).get("hp"))
        history.append({"who": "你", "text": message})
        history.append({"who": "AI", "text": said})

    last = history[-1]["text"]
    if "60" not in last:
        print("!! 最后一句没记住上一轮改成了 60：%r" % last[:80])
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
