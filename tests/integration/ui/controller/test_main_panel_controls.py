"""主面板顶栏与状态行的按钮（**集成测试**，只点界面上的东西）。

覆盖：状态行的「读状态」、导航条的「伤害计算」、锁图标。以前这三处只测过 controller
的 Slot，**按钮到 Slot 那一跳没人跑过**（点错了目标、锁图标点在别的地方、开了伤害
计算却没建窗口，都测不到）。

标准见 `tests/integration/README.md`：抓图/模型/找窗口是外部边界，用替身；
断言读公开属性（`controller.statusData / statusLocked`、`window.battleWindow / battleRows`）。
"""

import numpy as np

from chaita.game import read as game_read

from ... import helpers


def _window(monkeypatch=None):
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    # 状态行是缓存属性（`statusData`），要靠信号刷出来；不然那一行是隐藏的，
    # 隐藏行上的锁图标根本点不到。
    controller.statusTextChanged.emit()
    helpers.APP.processEvents()
    return controller, engine, window


def test_status_refresh_button_reads_the_person_panel(monkeypatch):
    """测什么：点状态行那个刷新 → 真的去抓一帧、读人物面板，数值写回状态行。

    走过的界面：主界面 → 状态行右侧的刷新按钮 →（桩）抓图 + 读人物 → 状态行。
    """
    controller, engine, window = _window()
    controller._start_thread = lambda target, args=(): target(*args)
    img = np.zeros((20, 20, 3), np.uint8)
    # 找窗口这一步也得桩掉：真去问 Windows 有没有游戏窗口，机器上开没开决定测试结果
    from chaita.game import towers
    helpers.fake_game_window(monkeypatch, towers.H5_MOTA.process)
    monkeypatch.setattr(game_read, "grab_window", lambda p: img)
    monkeypatch.setattr(game_read, "read_person",
                        lambda image, api_key=None: {"hp": "842", "atk": "13"})
    import chaita.ui.controller.status as status_mod
    monkeypatch.setattr(status_mod, "_api_key", lambda: "test-key")

    helpers.click_item(window, helpers.find_item(window, "statusRefresh"))
    # 读回来的结果走 uiCall（队列连接）排回界面线程：等它落地
    helpers.wait_for(
        lambda: str(controller.statusData.get("hp") or "") == "842", timeout=2.0)

    assert str(controller.statusData["hp"]) == "842"
    assert str(controller.statusData["atk"]) == "13"


def test_battle_button_opens_the_battle_window():
    """测什么：点导航条的 ⚔ → 开出伤害计算窗口，里面已经有一行空计划。

    走过的界面：主界面导航条（伤害计算按钮）→ 伤害计算窗口。
    """
    controller, engine, window = _window()
    assert window.property("battleWindow") is None

    helpers.click_item(window, helpers.find_item(window, "battleOpen"))
    helpers.APP.processEvents()

    value = window.property("battleWindow")
    value = value.toQObject() if hasattr(value, "toQObject") else value
    assert value is not None
    rows = window.property("battleRows")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
    assert len(rows) == 1 and rows[0]["steps"] == []


def test_status_lock_badge_toggles_the_lock():
    """测什么：点状态行那个锁图标 → 锁上；再点一下 → 解锁。

    走过的界面：主界面 → 状态行的锁图标（点两次）。
    """
    controller, engine, window = _window()
    assert controller.statusLocked is False

    helpers.click_item(window, helpers.find_item(window, "statusLock"))
    assert controller.statusLocked is True

    helpers.click_item(window, helpers.find_item(window, "statusLock"))
    assert controller.statusLocked is False

