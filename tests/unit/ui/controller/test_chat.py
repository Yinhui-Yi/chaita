"""对话单元测试（`chaita/ui/controller/chat.py`）。

真值来自规则：空话不发、忙时提示、迟到结果按序号丢掉、聊天记录最多留 40 条。
"""

from unittest.mock import Mock

from chaita.ui.controller.chat import CHAT_LOG_MAX, ChatMixin


class _NoTimer:
    @staticmethod
    def singleShot(ms, fn):
        return None


class Fake(ChatMixin):
    def __init__(self):
        self._chat_reply = ""
        self.chatReplyChanged = Mock()
        self._chat_log = []
        self.chatLogChanged = Mock()
        self._chatting = False
        self.chattingChanged = Mock()
        self._error_text = ""
        self._last_tower = None
        self._last_foreground = ""
        self._chat_token = 0
        self._last_status = {}
        self.statusTextChanged = Mock()

    def _apply_status(self, s):
        pass

    def _start_thread(self, target, args=()):
        self._started = (target, args)


def test_log_appends_and_skips_empty():
    c = Fake()
    c._log("你", "   ")
    assert c._chat_log == []
    c._log("你", "hello", tone="danger")
    assert c._chat_log[-1]["who"] == "你"
    assert c._chat_log[-1]["text"] == "hello"
    assert c._chat_log[-1]["tone"] == "danger"
    assert "at" in c._chat_log[-1]


def test_log_trims_to_max():
    c = Fake()
    for i in range(CHAT_LOG_MAX + 10):
        c._log("你", str(i))
    assert len(c._chat_log) == CHAT_LOG_MAX
    assert c._chat_log[-1]["text"] == str(CHAT_LOG_MAX + 9)


def test_say_sets_reply_and_emits():
    c = Fake()
    c._say("hi")
    assert c._chat_reply == "hi"
    assert c.chatReplyChanged.emit.called


def test_tower_for_chat_last_tower():
    c = Fake()
    c._last_tower = "T"
    assert c._tower_for_chat() == "T"


def test_tower_for_chat_falls_back(monkeypatch):
    import chaita.game.capture as cap
    fake = object()
    monkeypatch.setattr(cap, "find_target", lambda towers, fg: fake)
    c = Fake()
    assert c._tower_for_chat() is fake


def test_send_chat_empty_is_noop():
    c = Fake()
    c.sendChat("   ")
    assert c._chat_token == 0
    assert c._chatting is False


def test_send_chat_busy_prompts():
    c = Fake()
    c._chatting = True
    c.sendChat("hi")
    assert c._chat_reply == "上一句还在处理，稍等一下。"


def test_send_chat_starts(monkeypatch):
    import chaita.ui.controller.chat as chat
    monkeypatch.setattr(chat, "QTimer", _NoTimer)
    c = Fake()
    c.sendChat("hi")
    assert c._chatting is True
    assert c._chat_token == 1
    assert c._chat_log[0]["who"] == "你"
    assert c._chat_log[0]["text"] == "hi"


def test_chat_timeout_stale_is_noop():
    c = Fake()
    c._chat_token = 5
    c._chatting = True
    c._chat_timeout(3)
    # 旧的那次超时不能把新的一次对话标成"超时"
    assert c._chatting is True
    assert c._chat_reply == ""


def test_chat_timeout_valid_reports():
    c = Fake()
    c._chat_token = 5
    c._chatting = True
    c._chat_timeout(5)
    assert c._chatting is False
    assert "60 秒" in c._chat_reply


def test_chat_done_stale_is_noop():
    c = Fake()
    c._chat_token = 5
    c._chat_done("late", token=3)
    assert c._chat_reply == ""


def test_chat_done_with_status_update():
    c = Fake()
    c._chat_token = 1
    c._chat_done("改好了", token=1, status_updated=True)
    assert c._chat_reply == "改好了"
    assert c._chatting is False
    assert c._chat_log[-1]["text"] == "改好了"
    assert c.statusTextChanged.emit.called
