"""启动/收尾链路（**集成测试**）：`_teardown` 按顺序拆真窗口，不崩、不泄漏。

真对象：Controller + QML 引擎 + 真窗口（`helpers.make_controller`）。这条链验证"拆的顺序对、
拆完真的没了"。

**为什么这里直调 `startup._teardown(...)`**：它的真实触发是"进程退出"，没有可点的按钮，
没法用鼠标事件驱动 —— 和 README 里 `storeRoute()` 那条豁免同一类，写在这里免得下次被
当成"直调私有函数"删掉。

测什么：收尾之后 ① `controller._closing` 已经是真（定时器/线程先停）② 窗口、引擎、
controller 都**真的**销毁了（再碰就是 "对象已删除"，这正是收尾要防的那种访问）。

交互顺序：没有界面动作 —— 程序退出时按 startup.py 注释里的顺序拆：停定时器/线程 →
关窗 → 真删 QML → 断开 controller → 删引擎/controller。
"""

import pytest

import chaita.ui.startup as startup

from .. import helpers


def test_teardown_runs_against_real_objects():
    """测什么：拿真窗口真引擎跑一遍收尾，顺序对、拆干净（见文件头）。"""
    controller, engine, window = helpers.make_controller()

    startup._teardown(helpers.APP, engine, window, controller)

    # 1) 线程/定时器先停：关掉了就不会再有后台线程往回发信号
    assert controller._closing is True
    # 2) QML 真的销毁了：再碰窗口就是"对象已删除"
    with pytest.raises(RuntimeError):
        window.property("collapsed")
    # 3) 引擎和 controller 也销毁了
    with pytest.raises(RuntimeError):
        engine.rootObjects()
    with pytest.raises(RuntimeError):
        controller.property("reading")
