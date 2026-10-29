"""失败现场落盘单元测试（`chaita/ui/toolkit/diagnostics.py`）。

真值来自规则：失败原因写进 docs/capture/last_error.txt，并记一条 trace。
文件 I/O 用 fake 替掉。
"""

import chaita.ui.toolkit.diagnostics as diag


class _F:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def write(self, s):
        self.sink.append(s)


def test_write_error_log_writes_headline_and_detail(monkeypatch):
    sink = []
    monkeypatch.setattr(diag.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(diag.os.path, "dirname", lambda p: "x")
    monkeypatch.setattr(diag.os.path, "join", lambda *a: "last_error.txt")
    monkeypatch.setattr("builtins.open", lambda *a, **k: _F(sink))
    monkeypatch.setattr(diag.time, "strftime", lambda *a: "T")
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    diag._write_error_log("读不到局面", "detail line")
    text = "".join(sink)
    assert "读不到局面" in text
    assert "detail line" in text


def test_write_error_log_truncates_detail(monkeypatch):
    sink = []
    monkeypatch.setattr(diag.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(diag.os.path, "dirname", lambda p: "x")
    monkeypatch.setattr("builtins.open", lambda *a, **k: _F(sink))
    monkeypatch.setattr(diag.time, "strftime", lambda *a: "T")
    import chaita.trace as trace
    notes = []
    monkeypatch.setattr(trace, "note",
                        lambda *a, **k: notes.append(k.get("detail")))
    diag._write_error_log("x", "d" * 500)
    # trace 那边只带前 300 字
    assert len(notes[0]) == 300


def test_write_error_log_swallows_io_error(monkeypatch):
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    monkeypatch.setattr(diag.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(diag.os.path, "dirname", lambda p: "x")
    notes = []
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note",
                        lambda event, **kw: notes.append((event, kw)))

    assert diag._write_error_log("x", "y") is None   # 落不了盘也不抛

    # 落不了盘的时候 trace 那条仍然要留（不然这次失败就完全没痕迹）
    assert notes and notes[0][0] == "read.error"
