"""agent 的唯一基元：Task（一次任务怎么跑）+ Session（一个会话里问几轮）。

为什么要有 Session：一次「读地图」要在**同一张图**上问两三个问题（层号 → 这层有哪些
怪 → 有没有资源）。每个问题各开一个会话，就是同一张 2 MB 截图重复上传、重复视觉
编码——慢是按调用次数翻倍的。会话把图留在上下文里，后续问题只发文字。

对外只有三个名字：`Task`、`Session`、`run()`。
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from agent_framework import Agent, ChatOptions, Content, Message
from agent_framework.openai import OpenAIChatClient

from ... import trace

MODEL = "deepseek-v4-flash-vision-exp"
BASE_URL = "https://api.deepseek.com/v1"
MAX_TOKENS = 12000

# 关思考：这个模型开着思考时实测 58-130 s，还会把输出预算全烧在推理上、正文空着；
# 关掉后 1-2 s。开关只能走请求体的 thinking 字段（框架的 ChatOptions 没有它，
# 用 extra_body 透传）。
QUIET_BODY = {"thinking": {"type": "disabled"}}


def key(api_key: str = None) -> str:
    from ... import config
    key = (api_key or config.api_key() or "").strip()
    if not key:
        raise RuntimeError("缺少 API key：在 config.yaml 填 api_key，"
                           "或设置环境变量 DEEPSEEK_API_KEY")
    return key


def png(image) -> bytes:
    import cv2
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("截图编码失败")
    return buf.tobytes()


@dataclass(frozen=True)
class Task:
    """一次任务的说明书：问什么、怎么解析、能不能用工具、要不要关思考。"""

    doc: str                       # instructions：一个任务一段话
    parse: Callable[[str], Any]    # 文本 → 结构
    tools: Sequence = ()           # ("look",) / ("look", "sprite")
    quiet: bool = False            # True = 关思考
    retries: int = 1


class Session:
    """一个会话：第一次 ask 带上图，之后只发文字。

    事件循环必须**整个会话共用一个**。以前每次 ask 都开一个 `asyncio.run()`，
    第二轮就炸：框架底下的 httpx 连接池挂在第一个循环上，循环一关，
    第二次请求报 `Event loop is closed`（实测：问第二句必定失败）。
    所以循环跟着会话走，用完 `close()`（也可以 `with Session(...)`）。
    """

    def __init__(self, doc: str, *, tools=(), quiet: bool = False,
                 api_key: str = None):
        client = OpenAIChatClient(model=MODEL, api_key=api_key or key(),
                                  base_url=BASE_URL)
        self._agent = Agent(client=client, instructions=doc or "",
                            tools=list(tools))
        self._session = self._agent.create_session()
        self._quiet = quiet
        self._loop = asyncio.new_event_loop()

    def ask(self, text: str, image=None, *, label: str = "ask"):
        """问一句。返回 (文字, 原始 response)；response 里有工具产物（图标等）。"""
        if self._agent is None:
            raise RuntimeError("会话已经关闭了，要用就新建一个 Session")
        contents = []
        if image is not None:
            contents.append(Content.from_data(data=png(image),
                                              media_type="image/png"))
        contents.append(Content.from_text(text))

        options = {"max_tokens": MAX_TOKENS, "store": False}
        if self._quiet:
            options["extra_body"] = QUIET_BODY

        started = time.time()
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        response = self._loop.run_until_complete(
            self._agent.run(Message(role="user", contents=contents),
                            session=self._session,
                            options=ChatOptions(**options)))
        out = getattr(response, "text", "") or ""
        trace.note("agent.reply", label=label,
                   seconds=round(time.time() - started, 1),
                   chars=len(out), head=out[:120])
        return out, response

    def close(self) -> None:
        """关会话：先把框架/httpx 的异步收尾跑完，再关循环。

        为什么讲究顺序：httpx 的 `AsyncClient.aclose()` 是**垃圾回收时**才排到循环上的
        任务。先关循环，它就变成"Task exception was never retrieved: Event loop is
        closed"的噪音（实测一次读取刷 3 条）。所以顺序是：
        丢引用 → gc 收集（任务这才会被创建）→ 让循环跑一轮 → 关循环。
        """
        loop = self._loop
        self._loop = None
        self._agent = None
        self._session = None
        if loop is None or loop.is_closed():
            return
        try:
            import gc
            gc.collect()
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
        loop.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False


def run(task: Task, message: str, image=None, *, api_key: str = None) -> Any:
    """一问一答：开一个会话、问一句、按 task.parse 解析（空答复按 retries 重试）。"""
    text = ""
    for _attempt in range(max(1, task.retries)):
        with Session(task.doc, tools=task.tools, quiet=task.quiet,
                     api_key=api_key) as session:
            text, _response = session.ask(message, image, label=_label(task))
        if text.strip():
            break
    return task.parse(text)


def _label(task: Task) -> str:
    head = (task.doc or "").strip().splitlines()
    return head[0][:16] if head else "ask"


def json_object(text: str) -> dict:
    """从模型输出里取第一个 JSON 对象（容忍 ```json 围栏和前后废话）。"""
    import json
    import re
    raw = str(text or "")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fenced:
        raw = fenced.group(1)
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def ask_json(session, question: str, *, label: str = "ask", image=None,
             retries: int = 1) -> dict:
    """要一行 JSON：模型先扯家常（关思考后它爱写长文）就在同一会话里再要一次。"""
    for attempt in range(max(1, retries + 1)):
        text = (question if attempt == 0
                else "只回那行 JSON，不要解释、不要描述画面。")
        out, _response = session.ask(text, image if attempt == 0 else None,
                                     label=label)
        data = json_object(out)
        if data:
            return data
    return {}
