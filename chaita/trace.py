"""一条极简的日志：写文件 + 有控制台就顺带打出去。

为什么不用标准库 logging：这个程序跑在 pythonw 下（没有控制台），要的只是
"出问题时能翻一张纸" —— 每次读取的窗口、判定结果、耗时、模型原始输出、报错，
一行一条追加到 logs/chaita.log 就够了。上 logging 的 handler 配置反而更绕。
"""

import json
import os
import sys
import time

from .paths import ROOT as _ROOT
_LOG_DIR = os.path.join(_ROOT, "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "chaita.log")

# 超过这个大小就换一个 .1 文件，避免无限长
_MAX_BYTES = 2 * 1024 * 1024


def _rotate_if_needed() -> None:
    try:
        if os.path.getsize(_LOG_PATH) <= _MAX_BYTES:
            return
    except OSError:
        return
    try:
        os.replace(_LOG_PATH, _LOG_PATH + ".1")
    except OSError:
        pass


def note(event: str, **fields) -> None:
    """记一条。fields 里别放整张图，放长度、名字、状态这类短信息。"""
    line = "%s\t%s\t%s\n" % (
        time.strftime("%Y-%m-%d %H:%M:%S"), event,
        json.dumps(fields, ensure_ascii=False, default=str))
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        _rotate_if_needed()
        with open(_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception:
        pass
    # 从控制台跑的时候也看得见（pythonw 下 stdout 是 None，直接跳过）
    try:
        if sys.stderr is not None:
            sys.stderr.write(line)
            sys.stderr.flush()
    except Exception:
        pass
