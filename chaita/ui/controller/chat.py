"""对话：跟玩家聊天用的输入框，顺带能按他一句话改记录。

owner："该功能不是单纯用于修改参数的！！它需要具有聊天功能！！"

所以这里是**一段持续的对话**，不是一张表单：

  · 每一句都留着（`_chat_log`），下一句把最近几轮当上下文发过去 ——
    玩家说"刚才那只怪"要能接住；
  · 不要求先点过「读取」：没有状态就传空 {}，没有塔就按前台窗口现找；
  · 读取期间照样能发（不再共用 `_reading`）；
  · 模型回了状态才改记录，只回话就只是回话。

两处兜底是防界面冻住，不是"读取依赖"：一句没回音 60 秒自己收尾、
迟到结果按序号丢掉（`_chat_token`）。
"""

from .. import qt_env  # noqa: F401  （Qt 路径必须先指好）

import time

from PySide6.QtCore import QTimer, Slot

from ..toolkit.api import _api_key

CHAT_TIMEOUT_MS = 60_000
# 界面上留多少条：40 条 = 20 个来回，够翻回去看，也不会把内存和 XHR 拖肥
CHAT_LOG_MAX = 40

YOU = "你"
AI = "AI"


class ChatMixin:
    def _get_chat_reply(self):
        return self._chat_reply

    def _get_error_text(self):
        return self._error_text

    def _get_chatting(self):
        return self._chatting

    def _get_chat_log(self):
        return list(self._chat_log)

    def _say(self, reply: str) -> None:
        """把一句话贴进对话记录（用户能看见，不再静默）。"""
        self._chat_reply = reply
        self.chatReplyChanged.emit()

    def _log(self, who: str, text: str, tone: str = "") -> None:
        """记一条进对话记录；只在 UI 线程调（列表要跟界面同步）。

        tone = "danger" 时界面会把这条画成红色（出错的话也留在对话里，
        不然用户只看到自己那句、然后什么都没有）。
        """
        text = (text or "").strip()
        if not text:
            return
        entry = {"who": who, "text": text, "at": time.strftime("%H:%M")}
        if tone:
            entry["tone"] = tone
        self._chat_log = self._chat_log + [entry]
        del self._chat_log[:-CHAT_LOG_MAX]
        self.chatLogChanged.emit()

    def _tower_for_chat(self):
        """发话时该读哪座塔：最近读过的那座，否则按前台窗口现找。"""
        if self._last_tower is not None:
            return self._last_tower
        from ...game import capture, towers
        return capture.find_target(towers.TOWERS, self._last_foreground or "")

    @Slot(str)
    def sendChat(self, text: str) -> None:
        """发一句：聊天 / 提问 / 指正都走这里，不需要先点「读取」。"""
        text = (text or "").strip()
        if not text:
            return
        if self._chatting:
            self._say("上一句还在处理，稍等一下。")
            return

        self._chat_token += 1
        token = self._chat_token
        self._chatting = True
        self._chat_reply = "正在回你…"
        self._log(YOU, text)
        self.chattingChanged.emit()
        # 历史要在追加本句**之前**取：本句会单独作为 message 发过去
        history = list(self._chat_log[:-1])
        self._start_thread(self._chat_worker, (text, token, history))
        QTimer.singleShot(CHAT_TIMEOUT_MS, lambda: self._chat_timeout(token))

    def _chat_timeout(self, token: int) -> None:
        """一句话等太久了：收尾并告诉用户，别让输入框一直冻着。"""
        if token != self._chat_token or not self._chatting:
            return
        self._chat_done("这次等了 60 秒没回音，可能卡住了；再发一次试试。",
                        token, tone="danger")

    def _chat_worker(self, message: str, token: int = 0, history=None) -> None:
        from ...game import read as game_read
        from ...game import towers as tower_mod

        def fail(reply: str) -> None:
            self._post(lambda: self._chat_done(reply, token, tone="danger"))

        try:
            # 找不到窗口也照样聊：没截图就当"看不见画面"的聊天，只是不能引用屏幕上的数字
            tower = self._tower_for_chat()
            image = None
            if tower is not None:
                image = game_read.grab_window(tower.process)
                if image is not None:
                    # 只要图，不需要重新切区域；resolve 顺带做归一化
                    _panel, _map_rect, image = tower_mod.resolve(tower, image)
            # 没读过就把状态当空的传：模型会照截图给一份完整字段
            status = dict(self._last_status or {})
            result = game_read.chat(image, status, message, history=history,
                                    api_key=_api_key())

            def finish():
                if "_error" in result:
                    self._chat_done("没回上来：%s" % result.get("_error"), token,
                                    tone="danger")
                    return
                corrected = result.get("status")
                if corrected:
                    self._last_status = corrected
                    if tower is not None:
                        self._last_tower = tower
                    self._apply_status(corrected)
                # 模型没写回话也得给一句，别让框里空着
                fallback = "已按你的说法修正。" if corrected else "我没听清，再说一遍？"
                self._chat_done(result.get("reply") or fallback, token,
                                status_updated=bool(corrected))

            self._post(finish)
        except Exception as exc:
            fail("没回上来：%s" % str(exc)[:120])

    def _chat_done(self, reply: str, token: int = 0,
                   status_updated: bool = False, tone: str = "") -> None:
        """一句收尾。

        tone 空 = 正常回话（进对话记录，聊天条那行清空）；
        tone = "danger" = 出错（留在聊天条那行不消失，玩家不用滚动也能看见）。
        """
        # 序号对不上 = 这是上一句的迟到结果，别覆盖新的一句
        if token and token != self._chat_token:
            return
        self._chat_reply = reply
        self._chatting = False
        self._log(AI, reply, tone)
        self.chattingChanged.emit()
        if status_updated:
            self.statusTextChanged.emit()
