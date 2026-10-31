"""对话输入框（**集成测试**，在真输入框里打字 + 回车 / 点发送）。

以前只测到 `controller.sendChat(...)` 这一层，**输入框和发送按钮的接线从没跑过** ——
键错了、空串没拦住、发完没清空，测试都看不见。

标准见 `tests/integration/README.md`。边界：模型和抓图是桩，Controller 和 QML 都是真的。
断言读公开属性（`controller.chatReply / statusData / chatting`、输入框的 text）。
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from chaita.game import capture as cap
from chaita.game import read as game_read
from chaita.game import towers

from ... import helpers


class _NoTimer:
    @staticmethod
    def singleShot(ms, fn):
        return None


def _window(monkeypatch, reply="改好了", patch=None):
    """起真 Controller + QML，把模型/抓图两处边界换成桩。"""
    controller, engine, window = helpers.make_controller()
    controller._start_thread = lambda target, args=(): target(*args)
    import chaita.ui.controller.chat as chat
    monkeypatch.setattr(chat, "QTimer", _NoTimer)
    monkeypatch.setattr(chat, "_api_key", lambda: "test-key")
    monkeypatch.setattr(cap, "find_target", lambda t, fg: towers.H5_MOTA)
    monkeypatch.setattr(game_read, "grab_window", lambda p: None)

    def fake_chat(image, status, message, history=None, api_key=None):
        # 模型只改它认出来的字段（这里由 `patch` 决定）
        return {"reply": reply, "status": patch or {}}

    monkeypatch.setattr(game_read, "chat", fake_chat)
    controller._last_status = {"hp": "1000"}
    controller.statusTextChanged.emit()
    helpers.APP.processEvents()
    return controller, engine, window


def _type_enter(window, text):
    """在对话输入框里打字，然后真的按回车。"""
    field = helpers.find_item(window, "chatInput")
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(field.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()
    return field


def test_chat_input_enter_sends_and_clears(monkeypatch):
    """测什么：输入框里打字回车 → 话发出去、模型回的字段写进状态、输入框清空。

    交互顺序：① 点对话输入框 ② 打字「生命是1200」③ 回车 →
    断言 `chatReply` 是模型回的那句、`statusData.hp` 变成 1200、输入框空。
    """
    controller, engine, window = _window(monkeypatch, reply="改好了",
                                        patch={"hp": "1200"})
    _type_enter(window, "生命是1200")

    assert controller.chatReply == "改好了"
    assert str(controller.statusData["hp"]) == "1200"
    # 发完清空输入框（不然下一次会带上刚才那句）
    assert helpers.find_item(window, "chatInput").property("text") == ""


def test_chat_send_button_sends(monkeypatch):
    """测什么：点右边那个发送按钮 → 一样发出去并清空输入框。

    交互顺序：① 输入框里打字 ② 点发送按钮 → 断言 `chatReply`、`statusData.atk`、
    输入框空。
    """
    controller, engine, window = _window(monkeypatch, reply="收到",
                                        patch={"atk": "95"})
    field = helpers.find_item(window, "chatInput")
    field.setProperty("text", "攻击95")
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "chatSend"))

    assert controller.chatReply == "收到"
    assert str(controller.statusData["atk"]) == "95"
    assert helpers.find_item(window, "chatInput").property("text") == ""


def test_empty_chat_is_not_sent(monkeypatch):
    """测什么：只打空格回车 → 不发给模型（没有回复、也没进"正在想"）。

    交互顺序：① 输入框里打三个空格 ② 回车 → 断言 `chatReply` 还是空、`chatting` 为假。
    """
    controller, engine, window = _window(monkeypatch)
    _type_enter(window, "   ")

    # 空白不发给模型：状态没动、也没有回过话
    assert controller.chatReply == ""
    assert controller.chatting is False
