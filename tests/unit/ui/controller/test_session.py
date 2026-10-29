"""会话恢复/丢弃单元测试（`chaita/ui/controller/session.py`）。

真值来自规则：恢复时把层/怪读进列表并重对齐旧名，丢弃时删文件、提示消失。
"""

from unittest.mock import Mock

from chaita.ui.controller.session import SessionMixin


class Fake(SessionMixin):
    def __init__(self, session=None):
        self._session = session
        self._session_hint = ""
        self.sessionHintChanged = Mock()
        self._monsters = []
        self._map_history = []
        self.monstersChanged = Mock()
        self.mapHistoryChanged = Mock()
        self._aligned = False

    def _align_floor_rows(self):
        self._aligned = True


def test_restore_session_loads_and_aligns(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    c = Fake(session={"monsters": [{"name": "血蚊"}],
                      "floors": [{"floor": "1"}]})
    c.restoreSession()
    assert c._monsters == [{"name": "血蚊"}]
    assert c._map_history == [{"floor": "1"}]
    assert c._aligned
    assert c._session == {}
    assert c.monstersChanged.emit.called


def test_restore_session_empty(monkeypatch):
    c = Fake(session={})
    c.restoreSession()
    assert c._session == {}
    assert c._session_hint == ""
    assert c.sessionHintChanged.emit.called


def test_discard_session_clears_and_removes_file(monkeypatch):
    import os
    removed = []
    monkeypatch.setattr(os, "remove", lambda p: removed.append(p))
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    c = Fake(session={"monsters": [{"name": "血蚊"}]})
    c.discardSession()
    assert c._session == {}
    assert c._session_hint == ""
    assert len(removed) == 1
