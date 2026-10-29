"""怪物拖拽排序单元测试（`chaita/ui/controller/monsters/drag.py`）。

真值来自规则：落点按行高算并夹在 0..count-1，松手或没行就收尾，原地不动不落库。
"""

from unittest.mock import Mock

from chaita.ui.controller.monsters.drag import DragMixin


class Fake(DragMixin):
    def __init__(self):
        self._mon_drag = None
        self._mon_drag_timer = Mock()
        self.monDragChanged = Mock()

    def moveMonster(self, f, t):
        self.moved = (f, t)


def test_mon_drag_start(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    c = Fake()
    c.monDragStart(2, 100.0, 30.0, 5)
    assert c._mon_drag["from"] == 2
    assert c._mon_drag["to"] == 2
    assert c._mon_drag["row"] == 30.0
    assert c._mon_drag_timer.start.called


def test_mon_drag_start_zero_count_noop():
    c = Fake()
    c.monDragStart(0, 0.0, 30.0, 0)
    assert c._mon_drag is None
    assert not c._mon_drag_timer.start.called


def test_mon_drag_finish_same_index_noop():
    c = Fake()
    c._mon_drag = {"from": 1, "to": 1, "top": 0, "row": 30, "count": 5}
    c.monDragFinish()
    assert not hasattr(c, "moved")


def test_mon_drag_finish_moves(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    c = Fake()
    c._mon_drag = {"from": 0, "to": 3, "top": 0, "row": 30, "count": 5}
    c.monDragFinish()
    assert c.moved == (0, 3)
    assert c._mon_drag is None


def test_tick_mon_drag_computes_index(monkeypatch):
    import chaita.ui.controller.monsters.drag as drag
    monkeypatch.setattr(drag, "_cursor_pos", lambda: (0, 130))
    monkeypatch.setattr(drag, "_cursor_down", lambda: True)

    class Screen:
        def devicePixelRatio(self):
            return 1.0

    class App:
        @staticmethod
        def primaryScreen():
            return Screen()

    monkeypatch.setattr(drag, "QGuiApplication", App)
    c = Fake()
    c._mon_drag = {"from": 0, "to": 0, "top": 100, "row": 30, "count": 5}
    c._tick_mon_drag()
    assert c._mon_drag["to"] == 1       # (130-100)//30
    assert c.monDragChanged.emit.called


def test_tick_mon_drag_mouse_up_finishes_and_moves(monkeypatch):
    import chaita.ui.controller.monsters.drag as drag
    monkeypatch.setattr(drag, "_cursor_pos", lambda: (0, 130))
    monkeypatch.setattr(drag, "_cursor_down", lambda: False)  # 松开

    class Screen:
        def devicePixelRatio(self):
            return 1.0

    class App:
        @staticmethod
        def primaryScreen():
            return Screen()

    monkeypatch.setattr(drag, "QGuiApplication", App)
    c = Fake()
    c._mon_drag = {"from": 0, "to": 0, "top": 100, "row": 30, "count": 5}
    c._tick_mon_drag()
    assert c._mon_drag is None
    assert c.moved == (0, 1)


def test_tick_mon_drag_none_stops_timer():
    c = Fake()
    c._tick_mon_drag()
    assert c._mon_drag_timer.stop.called
