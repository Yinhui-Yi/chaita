"""复现/回归：同一个会话里连问三句会不会报 `Event loop is closed`。

为什么留这个脚本（属于"先复现再修 bug"的证据）：
2026-10-26，「一次读取只开一个会话」改造之后，`Session.ask` 每次都用
`asyncio.run()` —— 每个问题一个新循环、用完就关。而框架底下的 httpx 连接池
挂在**第一个**循环上，于是第二句必炸：

    agent_framework.exceptions.ChatClientException:
        service failed to complete the prompt: Event loop is closed

这个错误只有在**真发请求**时才会出现（单测里的假 Agent 走不到 httpx），
所以留一个能直接跑的小探针：三句都通过 = 循环跟着会话走，没退回老写法。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\check_session_loop.py

不碰游戏窗口，只发一张 48×48 的纯色占位图。
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np                                        # noqa: E402

from chaita.game.agent import core                        # noqa: E402

TURNS = 3


def main() -> int:
    image = np.full((48, 48, 3), 40, np.uint8)
    with core.Session("你在看一张图。只回 JSON。", quiet=True) as session:
        for turn in range(TURNS):
            question = '只回 {"n": %d}，不要别的话。' % turn
            try:
                text, _ = session.ask(question, image if turn == 0 else None,
                                      label="loop%d" % turn)
            except Exception:
                print("第 %d 句失败：" % (turn + 1))
                traceback.print_exc()
                return 1
            print("第 %d 句 ok：%r" % (turn + 1, text[:60]))
    print("三句都通过：循环跟着会话走，没有 Event loop is closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
