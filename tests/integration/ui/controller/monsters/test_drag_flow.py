"""怪物行拖拽排序（`chaita/ui/controller/monsters/drag.py` + QML 里那条抓取手势）。

真值手算：3 只怪、第一行顶部在屏幕 y=100、行高 20 →
光标在 y=140 时落在第 (140-100)//20 = 2 行 → 松手后第一只挪到最后。

为什么不靠 QML 的鼠标事件：指针一离开那一行 Qt 就发 canceled（代码注释里写了实
测过），所以拖拽是 Python 每帧读系统光标 —— 测试也按这个口子喂光标。
"""

from unittest.mock import Mock

from .... import helpers                     # noqa: F401  （统一从这里起窗口）


def _controller(monsters=("血蚊", "铁卫", "小蝙蝠")):
    controller, engine, window = helpers.make_controller()
    controller._monsters = [{"name": name, "hp": "100"} for name in monsters]
    controller.monstersChanged.emit()
    helpers.APP.processEvents()
    return controller, engine, window


def _patch_cursor(monkeypatch, y, down=True, dpr=1.0):
    """拖拽每帧都读系统光标：这里喂假的（x 用不到）。"""
    import chaita.ui.controller.monsters.drag as drag_mod

    monkeypatch.setattr(drag_mod, "_cursor_pos", lambda: (0, y))
    monkeypatch.setattr(drag_mod, "_cursor_down", lambda: down)

    class Screen:
        def devicePixelRatio(self):
            return dpr

    monkeypatch.setattr(drag_mod.QGuiApplication, "primaryScreen",
                        staticmethod(lambda: Screen()), raising=False)


def _names(controller):
    return [m["name"] for m in controller._monsters]


def test_drag_moves_first_monster_to_last(monkeypatch):
    controller, engine, window = _controller()
    controller.monDragStart(0, 100.0, 20.0, 3)
    _patch_cursor(monkeypatch, 140)             # 第 2 行

    controller._tick_mon_drag()
    assert controller.monDragTo == 2

    controller.monDragFinish()                  # 松手落库
    assert _names(controller) == ["铁卫", "小蝙蝠", "血蚊"]


def test_drag_cursor_above_and_below_are_clamped(monkeypatch):
    controller, engine, window = _controller()
    controller.monDragStart(1, 100.0, 20.0, 3)

    _patch_cursor(monkeypatch, 0)               # 拖到列表上面
    controller._tick_mon_drag()
    assert controller.monDragTo == 0

    _patch_cursor(monkeypatch, 9999)            # 拖到列表下面
    controller._tick_mon_drag()
    assert controller.monDragTo == 2

    # 每一帧都按光标重算落点，**后面那帧赢** → 松手是 1 → 2
    controller.monDragFinish()
    assert _names(controller) == ["血蚊", "小蝙蝠", "铁卫"]


def test_drag_without_moving_keeps_order(monkeypatch):
    controller, engine, window = _controller()
    controller.monDragStart(0, 100.0, 20.0, 3)
    _patch_cursor(monkeypatch, 105)             # 还在第 0 行

    controller._tick_mon_drag()
    controller.monDragFinish()

    assert _names(controller) == ["血蚊", "铁卫", "小蝙蝠"]


def test_physical_cursor_is_scaled_by_dpr(monkeypatch):
    """光标是物理像素、窗口是逻辑像素：150% 缩放下要除回去。"""
    controller, engine, window = _controller()
    controller.monDragStart(0, 100.0, 20.0, 3)
    _patch_cursor(monkeypatch, 140 * 2, dpr=2.0)   # 物理 280 = 逻辑 140

    controller._tick_mon_drag()

    assert controller.monDragTo == 2


def test_drag_finishes_itself_when_button_released(monkeypatch):
    """松开事件可能送不到那一行：每帧发现鼠标松了就自己收尾。"""
    controller, engine, window = _controller()
    controller.monDragStart(0, 100.0, 20.0, 3)
    _patch_cursor(monkeypatch, 140, down=False)

    controller._tick_mon_drag()                 # 这一帧就该落库

    assert controller._mon_drag is None
    assert _names(controller) == ["铁卫", "小蝙蝠", "血蚊"]


def test_drag_finishes_when_cursor_read_fails(monkeypatch):
    import chaita.ui.controller.monsters.drag as drag_mod
    controller, engine, window = _controller()
    controller.monDragStart(0, 100.0, 20.0, 3)
    monkeypatch.setattr(drag_mod, "_cursor_pos",
                        lambda: (_ for _ in ()).throw(RuntimeError("没有桌面")))

    controller._tick_mon_drag()                 # 不炸，直接收尾

    assert controller._mon_drag is None


def test_drag_start_with_no_rows_does_nothing():
    controller, engine, window = _controller(monsters=())
    controller.monDragStart(0, 100.0, 20.0, 0)

    assert controller._mon_drag is None
    assert controller.monDragFrom == -1
    assert controller.monDragTo == -1


def test_drag_finish_without_start_does_nothing():
    controller, engine, window = _controller()
    controller.monDragFinish()                  # 没开始过 → 什么都不该发生
    assert _names(controller) == ["血蚊", "铁卫", "小蝙蝠"]

