"""对话 + 人物状态两条链路集成测试。

真值从规则手推：聊天纠错只改指出的字段、update 只覆盖读到值的字段。
模型/抓图是边界用 stub；Controller、_apply_person、_chat_done 都是真的。
"""

import numpy as np

from chaita.game import capture as cap
from chaita.game import read as game_read
from chaita.game import towers

from ... import helpers


class _NoTimer:
    @staticmethod
    def singleShot(ms, fn):
        return None


def test_send_chat_corrects_status_end_to_end(monkeypatch):
    controller, engine, window = helpers.make_controller()
    controller._start_thread = lambda target, args=(): target(*args)
    import chaita.ui.controller.chat as chat
    monkeypatch.setattr(chat, "QTimer", _NoTimer)
    monkeypatch.setattr(cap, "find_target",
                        lambda t, fg: towers.H5_MOTA)
    monkeypatch.setattr(game_read, "grab_window", lambda p: None)  # 没截图
    monkeypatch.setattr(game_read, "chat",
                        lambda image, status, message, history=None,
                        api_key=None: {"reply": "改好了",
                                       "status": {"hp": "1200"}})
    monkeypatch.setattr(chat, "_api_key", lambda: "test-key")

    controller._last_status = {"hp": "1000"}
    controller.sendChat("生命是1200")
    helpers.APP.processEvents()

    assert controller._chat_reply == "改好了"
    assert controller._last_status["hp"] == "1200"
    assert controller._chatting is False


def test_update_status_end_to_end(monkeypatch):
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

    controller._last_status = {"hp": "1000", "atk": "90"}
    controller.updateStatus()
    helpers.APP.processEvents()

    assert controller._last_status["hp"] == "900"
    assert controller._last_status["atk"] == "95"
    assert controller._updating is False


def test_status_lock_blocks_reading_update():
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000"}
    controller.toggleStatusLock()
    assert controller.statusLocked is True

    result = game_read.Reading(
        status={"hp": "999"}, map=None, name="t", kind="status",
        monsters=[], floor="1", items=[], grid={})
    controller._deliver(towers.H5_MOTA, result, seq=0)
    helpers.APP.processEvents()

    # 锁住后读取不改状态面板
    assert controller._last_status["hp"] == "1000"

    controller.toggleStatusLock()
    assert controller.statusLocked is False
