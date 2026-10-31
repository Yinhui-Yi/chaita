"""状态锁：锁住之后"读状态"不改人物面板（**集成测试**，真点击）。

标准见 `tests/integration/README.md`。边界：抓图和模型是桩；锁图标、刷新按钮、
`_apply_person` 都是真的。

**删掉的 2 条**（都直调 Slot，而且已经有真按钮的用例）：
  · `test_send_chat_corrects_status_end_to_end` —— 直调 `controller.sendChat(...)`；
    「对话里打字改状态」在 `test_chat_dock.py` 里是真输入框 + 真回车
  · `test_update_status_end_to_end` —— 直调 `controller.updateStatus()`；
    「点状态行的刷新读人物」在 `test_main_panel_controls.py` 里是真点按钮

原来第 3 条是 `controller.toggleStatusLock()` + 私有 `_deliver(...)` 直调，
现在改成：点状态行那个锁图标 → 点刷新（桩掉抓图/模型）→ 断言面板没被改 → 再点锁解锁。
"""

import numpy as np

from chaita.game import read as game_read
from chaita.game import towers

from ... import helpers


def _window(monkeypatch):
    """起真 Controller + QML，把抓图/找窗口/模型换成桩。"""
    controller, engine, window = helpers.make_controller()
    controller._start_thread = lambda target, args=(): target(*args)
    img = np.zeros((40, 40, 3), np.uint8)
    # 找游戏窗口要桩：不然这条测试取决于"这台机器上有没有真开着游戏"
    helpers.fake_game_window(monkeypatch, towers.H5_MOTA.process)
    monkeypatch.setattr(game_read, "grab_window", lambda p: img)
    monkeypatch.setattr(game_read, "read_person",
                        lambda image, api_key=None: {"hp": "900", "atk": "95"})
    import chaita.ui.controller.status as status_mod
    monkeypatch.setattr(status_mod, "_api_key", lambda: "test-key")

    controller._last_status = {"hp": "1000"}
    controller.statusTextChanged.emit()
    helpers.APP.processEvents()
    return controller, engine, window


def test_lock_badge_blocks_the_refresh_button(monkeypatch):
    """测什么：锁上之后点「读状态」→ 读回来的数值不写进面板；解锁后再点才写进去。

    交互顺序：① 点状态行的锁图标（锁上，`statusLocked` 为真）② 点状态行的刷新
    → 断言面板还是 1000（模型返回的 900 被拦掉）③ 再点锁图标解锁 ④ 再点刷新
    → 断言面板变成 900/95。
    """
    controller, engine, window = _window(monkeypatch)

    helpers.click_item(window, helpers.find_item(window, "statusLock"))
    assert controller.statusLocked is True

    helpers.click_item(window, helpers.find_item(window, "statusRefresh"))
    helpers.wait_for(lambda: controller.tasks != [], timeout=2.0)
    helpers.APP.processEvents()
    assert str(controller.statusData["hp"]) == "1000", "锁上之后不该被读取改掉"

    helpers.click_item(window, helpers.find_item(window, "statusLock"))
    assert controller.statusLocked is False

    helpers.click_item(window, helpers.find_item(window, "statusRefresh"))
    assert helpers.wait_for(
        lambda: str(controller.statusData.get("hp") or "") == "900",
        timeout=2.0), controller.statusData
    assert str(controller.statusData["atk"]) == "95"
