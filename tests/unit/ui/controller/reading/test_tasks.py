"""读取任务控制单元测试（`chaita/ui/controller/reading/tasks.py`）。

真值来自规则：取消标 cancelled、重试按原 mode（status 走更新、其余重读原图）。
"""

from unittest.mock import Mock

from chaita.ui.controller.reading.tasks import ReadingTasksMixin


class Fake(ReadingTasksMixin):
    def __init__(self):
        self._cancelled = set()
        self._tasks = []
        self.tasksChanged = Mock()
        self._monsters = []
        self._map_history = []
        self._last_foreground = ""

    def _set_task(self, task_id, **fields):
        self._task_set = (task_id, fields)

    def _load_task_src(self, task_id):
        return None

    def _start_task(self, task_id, image=None, mode="auto"):
        self._started = (task_id, image, mode)

    def updateStatus(self):
        self._updated = True


def test_cancel_task(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    c = Fake()
    c.cancelTask(5)
    assert 5 in c._cancelled
    assert c._task_set == (5, {"state": "cancelled", "text": "已取消"})


def test_retry_status_task_calls_update(monkeypatch):
    c = Fake()
    c._tasks = [{"id": 5, "mode": "status"}]
    c.retryTask(5)
    # 人物那条没有截图可复用：重试 = 扔掉旧任务 + 再读一次
    assert c._updated is True
    assert c._tasks == []


def test_retry_auto_task_restarts_with_mode(monkeypatch):
    c = Fake()
    c._tasks = [{"id": 5, "mode": "auto"}]
    c.retryTask(5)
    assert c._started[0] == 5
    assert c._started[2] == "auto"


# ---- 读取流水线的分支：每个"提前收手"都要说清原因，并且不能让按钮卡住 ----

from types import SimpleNamespace            # noqa: E402

import chaita.ui.controller.reading.tasks as tasks_mod  # noqa: E402


class Worker(ReadingTasksMixin):
    """把"排回界面线程"改成同步执行，`_finish` 记下来，别真去写日志。"""

    def __init__(self):
        self._cancelled = set()
        self._tasks = []
        self._monsters = []
        self._map_history = []
        self._last_foreground = ""
        self._active = 0
        self._reading = False
        self._error_text = ""
        self._status_text = ""
        self._chat_reply = ""
        self._tower_label = ""
        self._attr_text = ""
        self._items_text = ""
        self._gold_text = ""
        self._frame = 0
        self._task_seq = 0
        self._map_seq = 0
        self.tasksChanged = Mock()
        self.readingChanged = Mock()
        self.statusTextChanged = Mock()
        self.chatReplyChanged = Mock()
        self.task_sets = []
        self.finishes = []
        self.threads = []
        self.delivered = None
        self.items_task = None
        self.items_done = None

    def _set_task(self, task_id, **fields):
        self.task_sets.append((task_id, fields))

    def _post(self, call):
        call()

    def _start_thread(self, target, args=()):
        self.threads.append((target, args))

    def _job_done(self):
        self._active = max(0, self._active - 1)
        self._reading = self._active > 0

    def _finish(self, headline, detail, task_id=None):
        self.finishes.append((headline, detail, task_id))

    def _deliver(self, *args, **kwargs):
        self.delivered = (args, kwargs)

    def _apply_floor(self, *args, **kwargs):
        self.applied_floor = (args, kwargs)

    def _start_items_task(self, *args, **kwargs):
        self.items_task = (args, kwargs)

    def _finish_items_task(self, *args, **kwargs):
        self.items_done = (args, kwargs)


def _quiet(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def _tower(name="h5mota 魔塔", process="chrome.exe"):
    return SimpleNamespace(name=name, process=process)


class _Towers:
    def __init__(self, *towers):
        self.TOWERS = {"t%d" % i: t for i, t in enumerate(towers)}


class _Read:
    """假 game_read：各步行为由构造参数决定。"""

    def __init__(self, screen="map", floor="3", result=None, boom=None,
                 items=None, grab=None):
        self.screen = screen
        self.floor = floor
        self._result = result
        self._boom = boom
        self._items = items
        self._grab = grab
        self.calls = []

    def classify(self, image, api_key=None):
        if self._boom == "classify":
            raise RuntimeError("判图挂了")
        return self.screen

    def map_snapshot(self, target, image):
        return "snapshot"

    def read_floor(self, image, api_key=None):
        return self.floor

    def read(self, target, api_key=None, image=None, screen=None,
             on_floor=None, known=None):
        if self._boom == "read":
            raise RuntimeError("模型挂了")
        return self._result

    def grab_window(self, process):
        return self._grab


class _Capture:
    def __init__(self, target=None, image=None, boom=None):
        self.target = target
        self.image = image
        self._boom = boom
        self.grabbed = []

    def find_target(self, towers, foreground):
        return self.target

    def describe_failure(self, towers, foreground):
        return "刚才在前台的是：%s" % (foreground or "（没采样到）")

    def grab(self, process):
        self.grabbed.append(process)
        return self.image


class _IMG:
    shape = (10, 10, 3)


class _Winutil:
    def __init__(self, running=0):
        self.running = running

    def find_window(self, process):
        return 1 if self.running else None


def _result(kind="map", items=None, floor="3"):
    return SimpleNamespace(kind=kind, monsters=[], items=items or [],
                           status={"floor": floor})


def test_start_task_creates_row_and_starts_thread(monkeypatch):
    _quiet(monkeypatch)
    c = Worker()
    c._start_task(None)

    assert c._tasks[0]["state"] == "running"
    assert c._tasks[0]["mode"] == "auto"
    assert c._active == 1 and c._reading is True
    assert c.threads and c.threads[0][1][2] is None      # 还没抓图


def test_start_task_thread_failure_does_not_hang_button(monkeypatch):
    """线程都起不来时：把计数退掉、任务标失败，按钮不能永久卡在"读取中"。"""
    _quiet(monkeypatch)
    c = Worker()

    def boom(target, args=()):
        raise RuntimeError("线程起不来")

    c._start_thread = boom
    c._start_task(None)

    assert c._active == 0
    assert c._reading is False
    assert c.finishes[0][0] == "起不了读取线程"
    assert c.finishes[0][2] == c._tasks[0]["id"]


def test_capture_without_game_reports_foreground(monkeypatch):
    _quiet(monkeypatch)
    c = Worker()
    c._last_foreground = "msedge.exe"

    target, image = c._capture(1, 5, None, _Towers(_tower()), _Capture())

    assert (target, image) == (None, None)
    assert c.finishes[0][0] == "前台不是游戏窗口"
    assert "msedge.exe" in c.finishes[0][1]


def test_capture_grab_failure_reports_minimised(monkeypatch):
    _quiet(monkeypatch)
    c = Worker()
    target, image = c._capture(1, 5, None, _Towers(_tower()),
                               _Capture(target=_tower(), image=None))

    assert (target, image) == (None, None)
    assert c.finishes[0][0] == "抓不到画面"
    assert "最小化" in c.finishes[0][1]


def test_capture_hangs_thumbnail_on_task(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_save_thumb",
                        lambda image, name, width=900: "file:///thumb.png")
    c = Worker()
    target, image = c._capture(1, 5, None, _Towers(_tower()),
                               _Capture(target=_tower(), image=_IMG()))

    assert target is not None and isinstance(image, _IMG)
    assert (5, {"url": "file:///thumb.png"}) in c.task_sets


def test_read_worker_crash_still_finishes(monkeypatch):
    """任何异常都不能让按钮卡住：异常要报出来，finally 里必须 _job_done。"""
    _quiet(monkeypatch)
    c = Worker()
    c._active = 1
    c._capture = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("炸了"))

    c._read_worker(1, 5)

    assert c.finishes[0][0] == "读取异常"
    assert "炸了" in c.finishes[0][1]
    assert c._active == 0


def test_read_once_without_api_key_says_so(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "")
    c = Worker()

    assert c._read_worker_once(1, 5, _Read(), _Towers(), _Winutil(),
                              image=_IMG(), mode="auto") is None
    assert c.finishes[0][0] == "没配置 API key"


def test_read_once_picks_unique_running_tower(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    monkeypatch.setattr(tasks_mod, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks_mod, "_save_thumb", lambda *a, **k: "")
    tower = _tower()
    c = Worker()

    c._read_worker_once(1, 5, _Read(result=_result()), _Towers(tower),
                        _Winutil(running=1), image=_IMG(), mode="auto")

    assert c.delivered is not None                       # 读成功了
    assert c.delivered[0][0] is tower


def test_read_once_ambiguous_running_towers_refuses(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    c = Worker()
    c._last_foreground = ""

    c._read_worker_once(1, 5, _Read(), _Towers(_tower(), _tower()),
                        _Winutil(running=1), image=None, mode="auto")

    assert c.finishes[0][0] == "前台不是游戏窗口"
    assert "两个" not in c.finishes[0][1]                 # 文案用数字
    assert "同时开着 2 个" in c.finishes[0][1]


def test_read_once_image_missing_reports(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    c = Worker()
    read = _Read(grab=None)

    c._read_worker_once(1, 5, read, _Towers(_tower()), _Winutil(),
                        image=None, mode="auto", target=_tower())

    assert c.finishes[0][0] == "抓不到画面"


def test_read_once_classify_crash_falls_back_to_map(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    monkeypatch.setattr(tasks_mod, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks_mod, "_save_thumb", lambda *a, **k: "")
    c = Worker()

    c._read_worker_once(1, 5, _Read(boom="classify", result=_result()),
                        _Towers(_tower()), _Winutil(), image=_IMG(),
                        mode="auto", target=_tower())

    # 判图挂了就**当地图读**：结果照样交付，且不以"手册"身份走
    assert c.delivered is not None
    args, _kwargs = c.delivered
    assert args[0] is not None                 # target
    assert c.finishes == []                    # 没有走失败收尾


def test_read_once_monsters_mode_requires_manual(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    monkeypatch.setattr(tasks_mod, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks_mod, "_save_thumb", lambda *a, **k: "")
    c = Worker()
    read = _Read(screen="map")

    c._read_worker_once(1, 5, read, _Towers(_tower()), _Winutil(),
                        image=_IMG(), mode="monsters", target=_tower())

    assert c.finishes[0][0] == "现在不是怪物手册"
    assert c.delivered is None


def test_read_once_map_mode_rejects_manual(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    monkeypatch.setattr(tasks_mod, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks_mod, "_save_thumb", lambda *a, **k: "")
    c = Worker()

    c._read_worker_once(1, 5, _Read(screen="manual"), _Towers(_tower()),
                        _Winutil(), image=_IMG(), mode="map", target=_tower())

    assert c.finishes[0][0] == "现在是怪物手册"


def test_read_once_model_crash_reports_cannot_read(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    monkeypatch.setattr(tasks_mod, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks_mod, "_save_thumb", lambda *a, **k: "")
    c = Worker()

    entry = c._read_worker_once(1, 5, _Read(boom="read"), _Towers(_tower()),
                                _Winutil(), image=_IMG(), mode="auto",
                                target=_tower())

    assert c.finishes[0][0] == "读不到局面"
    assert entry == "s1"                                 # 建过的层号照旧返回


def test_read_once_without_items_starts_items_task(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    monkeypatch.setattr(tasks_mod, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks_mod, "_save_thumb", lambda *a, **k: "")
    c = Worker()

    c._read_worker_once(1, 5, _Read(result=_result(kind="map", items=[])),
                        _Towers(_tower()), _Winutil(), image=_IMG(),
                        mode="auto", target=_tower())

    args, kwargs = c.items_task                # 漏了资源才补问一次
    assert args[0] is not None                 # game_read
    assert args[2] == "k"                      # 用的是同一次读取的 key
    assert args[4] == 5                        # 挂在同一条任务上
    assert c.items_done is None


def test_read_once_with_items_skips_second_question(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(tasks_mod, "_api_key", lambda: "k")
    monkeypatch.setattr(tasks_mod, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks_mod, "_save_thumb", lambda *a, **k: "")
    c = Worker()

    c._read_worker_once(1, 5,
                        _Read(result=_result(kind="map",
                                             items=[{"name": "红宝石"}])),
                        _Towers(_tower()), _Winutil(), image=_IMG(),
                        mode="auto", target=_tower())

    assert c.items_task is None                          # 已经读过资源了
    args, kwargs = c.items_done
    assert args[0] == 5
    assert kwargs["got_items"] is True
    assert c.finishes == []                              # 不算失败


def test_finish_writes_error_log_and_keeps_reading_flag(monkeypatch):
    """失败只写红字和日志，不碰 `_reading`（并行时别的任务还在跑）。"""
    monkeypatch.setattr(tasks_mod, "_write_error_log",
                        lambda headline, detail: None)
    c = Worker()
    c._reading = True
    c.statusTextChanged = Mock()
    c.chatReplyChanged = Mock()

    tasks_mod.ReadingTasksMixin._finish(c, "抓不到画面", "窗口最小化了\n第二行",
                                        task_id=5)

    assert c.task_sets[0][0] == 5
    assert c.task_sets[0][1]["state"] == "failed"
    assert c.task_sets[0][1]["text"].startswith("抓不到画面：窗口最小化了")
    assert c._reading is True                            # 不许清掉
    assert "抓不到画面" in c._error_text


