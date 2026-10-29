"""agent 基元单元测试（`chaita/game/agent/core.py`）。

真值来自规则：key 没配就报错、JSON 容忍围栏/废话、标签取第一行、ask_json 会重试。
"""

import numpy as np

import chaita.game.agent.core as core


def test_json_object_plain():
    assert core.json_object('{"hp": 1}') == {"hp": 1}


def test_json_object_fenced():
    assert core.json_object('```json\n{"hp": 1}\n```') == {"hp": 1}


def test_json_object_with_noise_around():
    assert core.json_object('前面废话 {"hp": 1} 后面废话') == {"hp": 1}


def test_json_object_garbage_is_empty():
    assert core.json_object("not json") == {}


def test_json_object_non_dict_is_empty():
    assert core.json_object("[1, 2]") == {}


def test_key_uses_explicit_arg(monkeypatch):
    import chaita.config as config
    monkeypatch.setattr(config, "api_key", lambda: "")
    assert core.key("sk-x") == "sk-x"


def test_key_raises_when_missing(monkeypatch):
    import pytest

    import chaita.config as config
    monkeypatch.setattr(config, "api_key", lambda: "")
    with pytest.raises(RuntimeError):
        core.key(None)


def test_png_encodes(monkeypatch):
    import cv2

    class Buf:
        def tobytes(self):
            return b"PNG"

    monkeypatch.setattr(cv2, "imencode", lambda ext, img: (True, Buf()))
    assert core.png(np.zeros((2, 2, 3), np.uint8)) == b"PNG"


def test_png_failure_raises(monkeypatch):
    import cv2
    import pytest
    monkeypatch.setattr(cv2, "imencode", lambda ext, img: (False, None))
    with pytest.raises(RuntimeError):
        core.png(np.zeros((2, 2, 3), np.uint8))


def test_label_first_line():
    task = core.Task("第一行\n第二行", lambda t: t)
    assert core._label(task) == "第一行"


def test_label_empty_doc():
    task = core.Task("", lambda t: t)
    assert core._label(task) == "ask"


def test_ask_json_first_try_succeeds():
    class Session:
        def __init__(self):
            self.calls = []

        def ask(self, text, image=None, label="ask"):
            self.calls.append(text)
            return '{"hp": 1}', None

    s = Session()
    assert core.ask_json(s, "问一句") == {"hp": 1}
    assert len(s.calls) == 1


def test_ask_json_retries_when_garbage():
    class Session:
        def __init__(self):
            self.calls = []

        def ask(self, text, image=None, label="ask"):
            self.calls.append(text)
            return "not json", None

    s = Session()
    assert core.ask_json(s, "问", retries=1) == {}
    assert len(s.calls) == 2


class _Resp:
    def __init__(self, text):
        self.text = text


class _FakeAgent:
    def __init__(self):
        self.called_message = None
        self.called_options = None

    def run(self, message, session=None, options=None):
        self.called_message = message
        self.called_options = options
        return None


class _FakeLoop:
    def __init__(self, result):
        self.result = result
        self.closed = False
        self.ran = 0

    def run_until_complete(self, coro):
        self.ran += 1
        if hasattr(coro, "close"):
            coro.close()      # 别让 coroutine 泄漏成 "never awaited"
        return self.result

    def is_closed(self):
        return False

    def close(self):
        self.closed = True


def test_session_ask_builds_message_and_extracts_text(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    s = core.Session.__new__(core.Session)
    s._agent = _FakeAgent()
    s._session = object()
    s._quiet = False
    s._loop = _FakeLoop(_Resp("回答"))
    out, resp = s.ask("问一句", label="x")
    assert out == "回答"
    assert s._agent.called_message is not None
    assert s._agent.called_options["max_tokens"] == core.MAX_TOKENS


def test_session_ask_quiet_adds_extra_body(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    s = core.Session.__new__(core.Session)
    s._agent = _FakeAgent()
    s._session = object()
    s._quiet = True
    s._loop = _FakeLoop(_Resp(""))
    s.ask("问", label="x")
    assert s._agent.called_options["extra_body"] == core.QUIET_BODY


def test_session_close_releases_and_closes_loop(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    s = core.Session.__new__(core.Session)
    s._agent = object()
    s._session = object()
    loop = _FakeLoop(_Resp(""))
    s._loop = loop
    s.close()
    assert s._agent is None
    assert s._session is None
    assert s._loop is None
    assert loop.closed


def test_run_parses_result(monkeypatch):
    class FakeSession:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ask(self, message, image=None, label="ask"):
            return "answer", None

    monkeypatch.setattr(core, "Session", FakeSession)
    task = core.Task("doc", lambda t: {"parsed": t}, retries=1)
    assert core.run(task, "msg") == {"parsed": "answer"}
