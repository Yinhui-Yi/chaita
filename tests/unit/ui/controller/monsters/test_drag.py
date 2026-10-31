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


def test_tick_mon_drag_scales_the_physical_cursor_by_dpr(monkeypatch):
    """光标是物理像素、窗口是逻辑像素：150%/200% 缩放下要除回去。

    （原来在集成测试 test_drag_flow 里，那份整份删掉了——它直接调
    monDragStart/_tick_mon_drag/monDragFinish 并断言私有字段，不是集成测试。）
    """
    import chaita.ui.controller.monsters.drag as drag
    monkeypatch.setattr(drag, "_cursor_pos", lambda: (0, 260))
    monkeypatch.setattr(drag, "_cursor_down", lambda: True)

    class Screen:
        def devicePixelRatio(self):
            return 2.0

    class App:
        @staticmethod
        def primaryScreen():
            return Screen()

    monkeypatch.setattr(drag, "QGuiApplication", App)
    c = Fake()
    c._mon_drag = {"from": 0, "to": 0, "top": 100, "row": 30, "count": 5}
    c._tick_mon_drag()
    # 260 物理 / 2.0 = 逻辑 130 → (130-100)//30 = 1
    assert c._mon_drag["to"] == 1


def test_tick_mon_drag_finishes_when_the_cursor_cannot_be_read(monkeypatch):
    """读不到光标（没有桌面）也要收尾，不能把定时器挂在那儿一直转。"""
    import chaita.ui.controller.monsters.drag as drag

    def boom():
        raise RuntimeError("没有桌面")

    monkeypatch.setattr(drag, "_cursor_pos", boom)
    c = Fake()
    c._mon_drag = {"from": 0, "to": 0, "top": 100, "row": 30, "count": 5}
    c._tick_mon_drag()
    assert c._mon_drag is None

