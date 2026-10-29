"""线程与任务队列单元测试（`chaita/ui/controller/jobs.py`）。

真值来自规则：任务按 id 改状态并通知、ui 调用异常被吞并记日志、退出后不再排任务。
"""

from unittest.mock import Mock

from chaita.ui.controller.jobs import JobsMixin


class Fake(JobsMixin):
    def __init__(self):
        self._closing = False
        self._tasks = [{"id": 1, "state": "running"}]
        self.tasksChanged = Mock()
        self.uiCall = Mock()
        self._active = 2
        self._reading = True
        self.readingChanged = Mock()
        self._threads = []


def test_set_task_updates_and_notifies():
    c = Fake()
    c._set_task(1, state="done", text="ok")
    assert c._tasks[0]["state"] == "done"
    assert c._tasks[0]["text"] == "ok"
    assert c.tasksChanged.emit.called


def test_set_task_none_or_missing_id_is_noop():
    c = Fake()
    c._set_task(None, state="done")
    c._set_task(999, state="done")
    assert c._tasks[0]["state"] == "running"
    assert not c.tasksChanged.emit.called


def test_task_src_path():
    c = Fake()
    c._tasks = [{"id": 7, "src": "file:///x.png"}]
    assert c._task_src_path(7) == "file:///x.png"
    assert c._task_src_path(99) == ""


def test_run_ui_call_swallows_error(monkeypatch):
    notes = []
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note",
                        lambda event, **kw: notes.append((event, kw)))
    c = Fake()

    def boom():
        raise Exception("x")

    c._run_ui_call(boom)                       # 不抛
    # 吞掉可以，但**必须留痕**：以前这里的异常是静默的，出问题查不到
    assert notes and notes[0][0] == "ui.call_error"


def test_run_ui_call_runs_the_call():
    c = Fake()
    ran = []
    c._run_ui_call(lambda: ran.append(1))
    assert ran == [1]


def test_post_emits_when_open():
    c = Fake()
    c._post(lambda: None)
    assert c.uiCall.emit.called


def test_post_skips_when_closing():
    c = Fake()
    c._closing = True
    c._post(lambda: None)
    assert not c.uiCall.emit.called


def test_job_done_decrements_active():
    c = Fake()
    c._job_done()
    assert c._active == 1
    assert c._reading is True
    c._job_done()
    assert c._active == 0
    assert c._reading is False


def test_start_thread_registers_daemon(monkeypatch):
    import threading
    made = []

    class FT:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon
            made.append(self)

        def start(self):
            self.started = True

    monkeypatch.setattr(threading, "Thread", FT)
    c = Fake()
    c._start_thread(lambda: None)
    assert len(made) == 1
    assert made[0].daemon is True
    assert made[0].started
    assert len(c._threads) == 1


def test_start_thread_does_nothing_when_closing(monkeypatch):
    """已经在退出：不许再起线程（线程回来会往已销毁的窗口里发信号）。"""
    import threading
    made = []

    class FT:
        def __init__(self, target, daemon):
            made.append(self)

        def start(self):
            raise AssertionError("退出中不该起线程")

    monkeypatch.setattr(threading, "Thread", FT)
    c = Fake()
    c._closing = True
    c._start_thread(lambda: None)
    assert made == []
    assert c._threads == []


def test_thread_takes_itself_out_of_the_list(monkeypatch):
    """线程跑完要把自己从 `_threads` 里摘掉，否则退出时会一直等一堆死线程。"""
    import threading
    ran = []

    class FT:
        def __init__(self, target, daemon):
            self.target = target

        def start(self):
            self.target()            # 立刻跑（模拟线程体执行完）

    monkeypatch.setattr(threading, "Thread", FT)
    c = Fake()
    c._start_thread(lambda: ran.append(1))
    assert ran == [1]
    assert c._threads == []


def test_load_task_src_returns_none_when_missing():
    c = Fake()
    c._tasks = [{"id": 1, "src": ""}]
    assert c._load_task_src(1) is None      # 没有原图 → None（调用方退回重新抓屏）
    c._tasks = [{"id": 2, "src": "file:///根本没有这个文件.png"}]
    assert c._load_task_src(2) is None      # 文件没了也不能炸


def test_log_prints(monkeypatch):
    import chaita.ui.controller.jobs as jobs_mod
    printed = []
    monkeypatch.setattr(jobs_mod, "print",
                        lambda *a, **k: printed.append(a), raising=False)
    Fake().log("hello")
    assert printed == [("[chaita] hello",)]
