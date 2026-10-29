"""资源合并单元测试（`chaita/ui/controller/reading/items.py`）。

真值来自规则：资源按名字合并、用户勾过/换过的图不被冲掉、读到/没读到决定任务状态。
"""

from unittest.mock import Mock

from chaita.ui.controller.reading.items import ReadingItemsMixin


class Fake(ReadingItemsMixin):
    def __init__(self, history=None):
        self._map_history = history or []
        self.mapHistoryChanged = Mock()
        self._cancelled = set()
        self._tasks = []
        self.tasksChanged = Mock()

    def _fill_item_display(self, row):
        return row

    def _start_thread(self, run):
        self.thread = run

    def _post(self, fn):
        fn()

    def _set_task(self, task_id, **fields):
        self._task_set = (task_id, fields)


def test_start_items_task_no_floor_is_noop():
    c = Fake()
    c._start_items_task(None, None, "k", "", None)
    assert not hasattr(c, "thread")


def test_attach_items_merges_by_name_and_keeps_user_flags(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    c = Fake(history=[{"floor": "1",
                       "items": [{"name": "红宝石", "icon": "gem_red",
                                  "done": True}]}])
    c._attach_items("1", [{"name": "红宝石", "count": 2},
                          {"name": "血瓶", "count": 1}])
    items = c._map_history[0]["items"]
    by_name = {i["name"]: i for i in items}
    assert by_name["红宝石"]["done"] is True       # 勾过的不冲掉
    assert by_name["红宝石"]["icon"] == "gem_red"  # 换过的图不冲掉
    assert by_name["红宝石"]["count"] == 2
    assert "血瓶" in by_name


def test_finish_items_task_got_items(monkeypatch):
    c = Fake()
    c._finish_items_task(1, "1", got_items=True)
    assert c._task_set == (1, {"state": "done", "text": "1"})


def test_finish_items_task_none_got(monkeypatch):
    c = Fake()
    c._finish_items_task(1, "1", got_items=False)
    assert c._task_set == (1, {"state": "failed", "text": "1（资源没读到）"})


def test_finish_items_task_cancelled_is_noop():
    c = Fake()
    c._cancelled = {1}
    c._finish_items_task(1, "1", got_items=True)
    assert getattr(c, "_task_set", None) is None


# ---- 真的跑一趟"补问资源" ----

class _Reader:
    def __init__(self, items=None, boom=False):
        self.items = items or []
        self.boom = boom
        self.asked = 0

    def read_items(self, image, api_key=None):
        self.asked += 1
        if self.boom:
            raise RuntimeError("模型挂了")
        return self.items


def _quiet(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def test_items_task_attaches_and_marks_done(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1", "items": []}])
    reader = _Reader(items=[{"name": "红宝石", "count": 2}])

    c._start_items_task(reader, "IMG", "k", "1", task_id=7)
    c.thread()                                   # 同步跑"后台"

    assert reader.asked == 1
    assert c._map_history[0]["items"][0]["name"] == "红宝石"
    assert c._task_set == (7, {"state": "done", "text": "1"})


def test_items_task_reports_failure_when_model_crashes(monkeypatch):
    """资源一条都没读到时不能打勾：标失败，用户能点「重试」。"""
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1", "items": []}])

    c._start_items_task(_Reader(boom=True), "IMG", "k", "1", task_id=7)
    c.thread()

    assert c._map_history[0]["items"] == []
    assert c._task_set[1]["state"] == "failed"
    assert c._task_set[1]["text"] == "1（资源没读到）"


def test_items_task_with_empty_answer_marks_failed(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1", "items": []}])

    c._start_items_task(_Reader(items=[]), "IMG", "k", "1", task_id=7)
    c.thread()

    assert c._task_set[1]["state"] == "failed"


def test_attach_items_ignores_empty_and_unknown_floor(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "2", "items": []}])

    c._attach_items("1", [{"name": "红宝石"}])    # 层不存在
    c._attach_items("2", [])                      # 一条都没有
    assert c._map_history[0]["items"] == []
