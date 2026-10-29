"""对话：玩家在底部输入框里跟你说话 —— 聊天、问事、顺手指正记录里的数字。

它**不是**改参数的表单：玩家可以问"这层还有几个怪""我刚读到什么"，
也可以只是骂一句"这塔好难"。纠正记录只是它能做的其中一件，不是唯一一件。

两条产品红线写进了 prompt：
  · 只给信息，不给决策（打不打、走不走是玩家的乐趣）；
  · 看不清就说看不清，不许编。
"""

import json
import re

from .... import trace
from .. import core

# 带上多少轮历史。八轮够把"我刚说的那只怪"接住，又不至于把 prompt 拖长。
MAX_HISTORY = 8
# 单条历史截断：玩家复述一大段榜单时，别让它占满上下文
MAX_TURN_CHARS = 200

PROMPT = """你是「拆塔辅助」里的对话助手。玩家在玩魔塔，底部输入框就是跟你说话的地方。

怎么回：
  · 像人说话：一两句，最多三行。不要 markdown、不要列表、不要复述规则；
  · 只说信息：截图上的状态、你替他记着的怪/资源/楼层；
  · 不给建议、不替他做决定 —— 打不打、走不走是他的乐趣；
  · 看不清就说看不清，别编。

如果他是在**纠正你的记录**（例如「生命是1200」「黄钥匙2把」），先回一句话，
再另起一行输出这行 JSON（只改他指出的，其余照抄当前状态；没有的写 null）：

{"status":{"floor":"当前层","hp":生命,"atk":攻击,"def":防御,"mdef":魔防,"level":等级,
"exp":经验,"gold":金币,"next":NEXT,"keys":{"yellow":0,"blue":0,"red":0,"green":0},
"special":{"po":0,"zha":0,"fei":0}}}

只是聊天，就不要输出 JSON。
"""

_FENCE = re.compile(r"```(?:json)?\s*\{.*?\}\s*```", re.S)
_OBJECT = re.compile(r"\{.*\}", re.S)
# "像状态 JSON" 的样子：模型偶尔把 JSON 写坏（多写一个对象、带注释、漏引号），
# 解析不出来也不能让它留在回话里 —— 用户会看到一长串字段挤在一行、前面还空一行
# （用户："我告诉AI更新人物状态，我看你所有的东西都写在一行，还空了一行"）。
_STATUS_HINT = re.compile(r'"status"\s*:', re.I)


def _public(status: dict) -> dict:
    """去掉内部字段（`_raw` 这类），只留面板上真有的。"""
    return {key: value for key, value in (status or {}).items()
            if not key.startswith("_")}


def _clean_reply(text: str) -> str:
    """回话收拾干净：去掉空行（那份 JSON 前面通常留一个空行）、行首尾空白。"""
    lines = [line.strip() for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line)


def _split_json(text: str):
    """把"回话"和"那行 JSON"分开。JSON 可能裸着，也可能被 ``` 包着。"""
    raw = str(text or "")
    fenced = _FENCE.search(raw)
    if fenced:
        data = core.json_object(fenced.group(0))
        if data:
            return _clean_reply(raw[:fenced.start()] + raw[fenced.end():]), data
    matched = _OBJECT.search(raw)
    if matched:
        chunk = matched.group(0)
        data = core.json_object(chunk)
        if data:
            return _clean_reply(raw[:matched.start()] + raw[matched.end():]), data
        if _STATUS_HINT.search(chunk):
            # 写坏了的状态 JSON：整段从回话里拿掉，只当"这次没改记录"
            return _clean_reply(raw[:matched.start()] + raw[matched.end():]), {}
    return _clean_reply(raw), {}


def _parse(text: str) -> dict:
    """回话是正文；JSON 只是可选附件（有就当纠错，没有就是纯聊天）。"""
    body, data = _split_json(text)
    reply = _clean_reply(data.get("reply") or "")
    corrected = data.get("status")
    status = (_public(corrected)
              if isinstance(corrected, dict) and corrected else None)
    reply = reply or body
    if not reply and status is None:
        return {"_error": "模型没有回话", "_raw": text or ""}
    return {"status": status, "reply": reply, "_raw": text or ""}


def _history_text(history) -> str:
    """把之前的对话排成几行，让模型接得住"刚才那只怪"这种指代。"""
    lines = []
    for turn in list(history or [])[-MAX_HISTORY:]:
        who = "玩家" if turn.get("who") == "你" else "我"
        said = str(turn.get("text") or "").strip()[:MAX_TURN_CHARS]
        if said:
            lines.append("%s：%s" % (who, said))
    return "\n".join(lines)


def reply(image, status: dict, message: str, history=None, api_key: str = None,
          tries: int = 2) -> dict:
    """回一句话（必要时顺带改记录）。

    返回 {"status","reply","_raw"}（不改记录时 status 是 None）或 {"_error","_raw"}。
    """
    parts = ["当前记录：%s" % json.dumps(_public(status), ensure_ascii=False)]
    if image is None:
        parts.append("（这次没有截图，看不到画面，只能靠记录和对话来回答）")
    earlier = _history_text(history)
    if earlier:
        parts.append("之前的对话：\n%s" % earlier)
    parts.append("玩家刚说：%s" % message)
    parts.append("请回答。")

    task = core.Task(PROMPT, _parse, quiet=True, retries=max(1, tries))
    result = core.run(task, "\n\n".join(parts), image, api_key=api_key)
    if "_error" in result:
        trace.note("agent.chat_failed", error=result["_error"][:80])
    return result
