"""对话解析单元测试（`chaita/game/agent/chat/reply.py`）。

真值来自规则：回话是正文、JSON 是可选附件、写坏的 JSON 从回话里拿掉、历史截断。
"""

import chaita.game.agent.chat.reply as rep


def test_public_filters_underscore():
    assert rep._public({"_raw": "x", "hp": 1}) == {"hp": 1}
    assert rep._public(None) == {}


def test_clean_reply_strips_blank_lines():
    assert rep._clean_reply("你好\n\n世界\n") == "你好\n世界"


def test_split_json_plain():
    body, data = rep._split_json('改了。\n{"status":{"hp":1200}}')
    assert body == "改了。"
    assert data["status"]["hp"] == 1200


def test_split_json_fenced():
    body, data = rep._split_json('改了。\n```json\n{"status":{"hp":1200}}\n```')
    assert body == "改了。"
    assert data["status"]["hp"] == 1200


def test_split_json_pure_chat():
    body, data = rep._split_json("纯聊天")
    assert body == "纯聊天"
    assert data == {}


def test_parse_pure_chat():
    out = rep._parse("这塔好难")
    assert out["reply"] == "这塔好难"
    assert out["status"] is None


def test_parse_with_correction():
    out = rep._parse('改成 1200。\n{"status":{"hp":1200}}')
    assert out["reply"] == "改成 1200。"
    assert out["status"] == {"hp": 1200}


def test_parse_empty_is_error():
    out = rep._parse("")
    assert "_error" in out


def test_history_text():
    h = [{"who": "你", "text": "第一只怪是什么"},
         {"who": "AI", "text": "是血蚊"}]
    text = rep._history_text(h)
    assert "玩家：第一只怪是什么" in text
    assert "我：是血蚊" in text


def test_history_text_truncates_long_turn():
    h = [{"who": "你", "text": "x" * 500}]
    text = rep._history_text(h)
    assert "x" * 201 not in text


# ---- 模型把 JSON 写坏 / 只回 JSON / 历史里有空轮 ----

def test_parse_reads_reply_key_in_json():
    out = rep._parse('{"reply":"刚记下了","status":{}}')
    assert out["reply"] == "刚记下了"
    assert out["status"] is None          # 空 status = 这次不改记录


def test_split_json_broken_status_is_stripped_from_reply():
    """写坏的状态 JSON 不能留在回话里（用户会看到一长串字段挤成一行）。"""
    body, data = rep._split_json('改好了。\n{"status": }')
    assert data == {}
    assert '"status"' not in body
    assert body == "改好了。"


def test_split_json_broken_fence_takes_first_object_and_drops_it():
    """规则：**先找到的那个 {} 说了算**；它坏了就整段丢掉，不会去捞后面的。

    宁可这次不改记录，也不能把一段写坏的 JSON 留进回话里。
    """
    body, data = rep._split_json(
        '改好了。\n```json\n{"status": }\n```\n{"status":{"hp":1200}}')
    assert data == {}
    assert '"status"' not in body.split("\n\n")[0] or "改好了。" in body


def test_history_text_skips_empty_turns():
    h = [{"who": "你", "text": "  "}, {"who": "你", "text": "第二句"}]
    assert rep._history_text(h) == "玩家：第二句"
    assert rep._history_text(None) == ""


# ---- 组 prompt + 调模型 ----

class _Task:
    def __init__(self, prompt, parse, quiet=True, retries=1):
        self.prompt = prompt
        self.parse = parse
        self.quiet = quiet
        self.retries = retries
        _Captured.task = self


class _Captured:
    task = None
    message = ""
    image = "unset"
    api_key = ""
    result = {"reply": "好", "status": None, "_raw": ""}


def _stub_core(monkeypatch, result=None):
    monkeypatch.setattr(rep.core, "Task", _Task)

    def fake_run(task, message, image, api_key=None):
        _Captured.message = message
        _Captured.image = image
        _Captured.api_key = api_key
        return dict(result if result is not None else _Captured.result)

    monkeypatch.setattr(rep.core, "run", fake_run)
    _Captured.result = result or {"reply": "好", "status": None, "_raw": ""}


def test_reply_builds_prompt_with_status_and_history(monkeypatch):
    _stub_core(monkeypatch)

    out = rep.reply("IMG", {"hp": 1000, "_raw": "内部"},
                    "生命是1200",
                    history=[{"who": "你", "text": "刚才那只怪"}],
                    api_key="k", tries=3)

    assert out["reply"] == "好"
    assert "当前记录" in _Captured.message
    assert '"hp": 1000' in _Captured.message
    assert "_raw" not in _Captured.message          # 内部字段不进 prompt
    assert "之前的对话：\n玩家：刚才那只怪" in _Captured.message
    assert "玩家刚说：生命是1200" in _Captured.message
    assert "没有截图" not in _Captured.message
    assert _Captured.image == "IMG"
    assert _Captured.api_key == "k"
    assert _Captured.task.retries == 3


def test_reply_without_image_says_so(monkeypatch):
    _stub_core(monkeypatch)
    rep.reply(None, {"hp": 1}, "这层还有几个怪")
    assert "这次没有截图" in _Captured.message


def test_reply_notes_failure(monkeypatch):
    _stub_core(monkeypatch, result={"_error": "模型没回话", "_raw": ""})
    notes = []
    import chaita.game.agent.chat.reply as rep_mod
    monkeypatch.setattr(rep_mod.trace, "note",
                        lambda event, **kw: notes.append((event, kw)))

    out = rep.reply("IMG", {}, "在吗")

    assert "_error" in out
    assert notes[0][0] == "agent.chat_failed"


def test_reply_retries_at_least_once(monkeypatch):
    _stub_core(monkeypatch)
    rep.reply("IMG", {}, "在吗", tries=0)
    assert _Captured.task.retries == 1      # tries=0 也要至少跑一次
