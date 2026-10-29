"""日志单元测试（`chaita/trace.py`）。

真值来自规则：note 一行一条追加、字段 JSON 化、超过 2MB 轮转成 .1。
文件/目录 I/O 全用 fake 替掉（不碰真实磁盘）。
"""

import io

import chaita.trace as trace


class _FakeFile:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def write(self, text):
        self.sink.append(text)


def _noop(*args, **kwargs):
    return None


def test_note_writes_event_and_fields(monkeypatch):
    sink = []
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: _FakeFile(sink))
    monkeypatch.setattr(trace.os, "makedirs", _noop)
    monkeypatch.setattr(trace, "_rotate_if_needed", _noop)
    trace.note("battle.compute", steps=2, total=540)
    line = "".join(sink)
    assert "battle.compute" in line
    assert '"steps": 2' in line
    assert '"total": 540' in line


def test_note_opens_for_append(monkeypatch):
    modes = []

    def _open(path, mode="r", *a, **k):
        modes.append(mode)
        return _FakeFile([])

    monkeypatch.setattr("builtins.open", _open)
    monkeypatch.setattr(trace.os, "makedirs", _noop)
    monkeypatch.setattr(trace, "_rotate_if_needed", _noop)
    trace.note("a")
    assert modes == ["a"]


def test_note_swallows_write_error(monkeypatch):
    """写失败不能把调用方带崩，而且**下一次还能照常写**。"""
    calls = []

    def _open(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("disk full")
        return _FakeFile([])

    monkeypatch.setattr("builtins.open", _open)
    monkeypatch.setattr(trace.os, "makedirs", _noop)
    monkeypatch.setattr(trace, "_rotate_if_needed", _noop)

    assert trace.note("a") is None      # 第一次：吞掉
    trace.note("b")                     # 第二次：照常写
    assert len(calls) == 2


def test_rotate_over_max_moves_to_dot1(monkeypatch):
    monkeypatch.setattr(trace.os.path, "getsize",
                        lambda p: 2 * 1024 * 1024 + 1)
    replaced = []
    monkeypatch.setattr(trace.os, "replace",
                        lambda src, dst: replaced.append(dst))
    trace._rotate_if_needed()
    assert replaced == [trace._LOG_PATH + ".1"]


def test_rotate_under_max_keeps_file(monkeypatch):
    monkeypatch.setattr(trace.os.path, "getsize", lambda p: 10)
    replaced = []
    monkeypatch.setattr(trace.os, "replace",
                        lambda *a: replaced.append(a))
    trace._rotate_if_needed()
    assert replaced == []               # 没超 2MB 就不动文件


def test_rotate_oserror_is_ignored(monkeypatch):
    monkeypatch.setattr(trace.os.path, "getsize",
                        lambda p: (_ for _ in ()).throw(OSError("no")))
    replaced = []
    monkeypatch.setattr(trace.os, "replace",
                        lambda *a: replaced.append(a))
    trace._rotate_if_needed()
    assert replaced == []               # 连文件多大都不知道 → 跳过轮转
