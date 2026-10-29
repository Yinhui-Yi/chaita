"""启动/收尾链路集成测试：`_teardown` 按顺序拆真窗口，不崩、不泄漏。

真对象：Controller + QML 引擎 + 窗口（helpers.make_controller）。这条链验证
"拆的顺序对、拆完真的没了"，具体顺序语义见 startup.py 的注释。
"""

import pytest

import chaita.ui.startup as startup

from .. import helpers


def test_teardown_runs_against_real_objects():
    controller, engine, window = helpers.make_controller()

    # 收尾顺序：停定时器/线程 → 关窗 → 真删 QML → 断开 controller → 删引擎/controller
    startup._teardown(helpers.APP, engine, window, controller)

    # 1) 线程/定时器先停：关掉了就不会再有后台线程往回发信号
    assert controller._closing is True
    # 2) QML 真的销毁了：再碰窗口就是"对象已删除"（这也正是收尾要防的那种访问）
    with pytest.raises(RuntimeError):
        window.property("collapsed")
    # 3) 引擎和 controller 也销毁了
    with pytest.raises(RuntimeError):
        engine.rootObjects()
    with pytest.raises(RuntimeError):
        controller.property("reading")
