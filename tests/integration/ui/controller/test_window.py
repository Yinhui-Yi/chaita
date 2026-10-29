"""窗口动画/拖拽入口链路集成测试（`chaita/ui/controller/window.py`）。

真值从规则手推：animateSize 记下目标尺寸+时长、dragStart/dragEnd 挂起/收尾拖拽。
数学插值（OutCubic）和光标换算在单测 test_window.py 里已覆盖，这里只测 @Slot 入口。
"""

from ... import helpers


def test_animate_size_sets_target():
    controller, engine, window = helpers.make_controller()
    controller.animateSize(400, 800, 100)
    assert controller._anim_to == (400, 800)
    assert controller._anim_ms == 100
    controller._anim.stop()               # 停掉动画定时器，别让它接着跑


def test_drag_start_end_pair():
    controller, engine, window = helpers.make_controller()
    controller.dragStart(10, 20)
    assert controller._drag_active is True
    assert controller._drag_offset == (10, 20)
    controller.dragEnd()
    assert controller._drag_active is False
