"""「已保存」回执单元测试（`chaita/ui/controller/floors/feedback.py`）。

真值来自规则：完成按钮回执写一句"已保存"，savedKey 让那一格闪一下、空了不再发信号。
"""

from unittest.mock import Mock

from chaita.ui.controller.floors.feedback import FeedbackMixin


class Fake(FeedbackMixin):
    def __init__(self):
        self._chat_reply = ""
        self.chatReplyChanged = Mock()
        self._saved_key = ""
        self.savedKeyChanged = Mock()


def test_mark_floor_saved(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    c = Fake()
    c.markFloorSaved("长安1")
    assert c._chat_reply == "已保存「长安1」"
    assert c.chatReplyChanged.emit.called


def test_mark_floor_saved_blank_is_noop(monkeypatch):
    c = Fake()
    c.markFloorSaved("   ")
    assert c._chat_reply == ""
    assert not c.chatReplyChanged.emit.called


def test_mark_saved_sets_key_and_clear_emits():
    c = Fake()
    c._mark_saved("mon", "地下30", 1)
    assert c._get_saved_key() == "mon:地下30:1"
    assert c.savedKeyChanged.emit.called
    c._clear_saved()
    assert c._get_saved_key() == ""


def test_clear_saved_when_empty_does_not_emit():
    c = Fake()
    c._clear_saved()
    assert not c.savedKeyChanged.emit.called
