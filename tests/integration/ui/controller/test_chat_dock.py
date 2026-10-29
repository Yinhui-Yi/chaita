"""对话输入框集成测试：在 QML 的输入框里真的打字 + 回车 / 点发送。

以前只测到 `controller.sendChat(...)` 这一层，**输入框和发送按钮的接线从没跑过** ——
键错了、空串没拦住、发完没清空，测试都看不见。

模型/抓图是边界上的桩；Controller 和 QML 都是真的。
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
    return controller, engine, window


def _type_enter(window, text):
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
    controller, engine, window = _window(monkeypatch, reply="改好了",
                                         patch={"hp": "1200"})
    _type_enter(window, "生命是1200")

    assert controller._chat_reply == "改好了"
    assert controller._last_status["hp"] == "1200"
    # 发完清空输入框（不然下一次会带上刚才那句）
    assert helpers.find_item(window, "chatInput").property("text") == ""


def test_chat_send_button_sends(monkeypatch):
    controller, engine, window = _window(monkeypatch, reply="收到",
                                         patch={"atk": "95"})
    field = helpers.find_item(window, "chatInput")
    field.setProperty("text", "攻击95")
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "chatSend"))

    assert controller._chat_reply == "收到"
    assert controller._last_status["atk"] == "95"
    assert helpers.find_item(window, "chatInput").property("text") == ""


def test_empty_chat_is_not_sent(monkeypatch):
    controller, engine, window = _window(monkeypatch)
    _type_enter(window, "   ")

    # 空白不发给模型：状态没动、也没有回过话
    assert controller._chat_reply == ""
    assert controller._chatting is False

