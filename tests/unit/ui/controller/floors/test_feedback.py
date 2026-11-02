"""「已存好」回执单元测试（`chaita/ui/controller/floors/feedback.py`）。

真值来自规则：savedKey 让那一格闪一下、空了不再发信号。
"""

from unittest.mock import Mock

from chaita.ui.controller.floors.feedback import FeedbackMixin


class Fake(FeedbackMixin):
    def __init__(self):
        self._saved_key = ""
        self.savedKeyChanged = Mock()


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
