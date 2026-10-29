"""刷新本层单元测试（`chaita/ui/controller/reading/scan.py`）。

真值来自规则：怪按手册归一、同一种只留一行、只更新数量不删旧行、数量取大。
"""

from unittest.mock import Mock

from chaita.ui.controller.reading.scan import ReadingScanMixin


class Fake(ReadingScanMixin):
    def __init__(self, history, monsters=None):
        self._map_history = history
        self._monsters = monsters or []
        self.mapHistoryChanged = Mock()
        self.countingChanged = Mock()
        self._counting_floor = ""

    def _fill_item_display(self, row):
        return row

    def _set_task(self, task_id, **fields):
        self._task_set = (task_id, fields)


def _quiet(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def test_apply_scan_updates_count(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1",
                       "mons": [{"name": "血蚊", "count": 1}], "items": []}],
             monsters=[{"name": "血蚊"}])
    c._apply_scan("1", [{"name": "血蚊", "count": 3}], items=[], grid={})
    assert c._map_history[0]["mons"] == [{"name": "血蚊", "count": 3}]


def test_apply_scan_aligns_model_guessed_name(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1",
                       "mons": [{"name": "红史莱姆", "count": 2}], "items": []}],
             monsters=[{"name": "红色史莱姆"}])
    c._apply_scan("1", [{"name": "红史莱姆", "count": 4}], items=[], grid={})
    assert c._map_history[0]["mons"] == [{"name": "红色史莱姆", "count": 4}]


def test_apply_scan_dedups_old_rows_keep_larger(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1",
                       "mons": [{"name": "血蚊", "count": 2},
                                {"name": "血蚊", "count": 5}], "items": []}],
             monsters=[{"name": "血蚊"}])
    c._apply_scan("1", [], items=[], grid={})   # 本次没读到怪
    mons = c._map_history[0]["mons"]
    assert len(mons) == 1
    assert mons[0]["count"] == 5


def test_apply_scan_drops_unmatched_when_handbook_known(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1", "mons": [], "items": []}],
             monsters=[{"name": "红色史莱姆"}])
    c._apply_scan("1", [{"name": "绿头怪", "count": 3}], items=[], grid={})
    assert c._map_history[0]["mons"] == []     # 对不上手册的怪不记


def test_start_scan_task_sets_counting(monkeypatch):
    c = Fake(history=[], monsters=[])
    c._start_thread = lambda run: setattr(c, "thread", run)
    c._start_scan_task("file:///x.png", "1", task_id=7)
    assert c._counting_floor == "1"
    assert c.countingChanged.emit.called
    assert hasattr(c, "thread")


def test_apply_scan_merges_items_by_icon(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[{"floor": "1", "mons": [],
                       "items": [{"name": "红宝石", "icon": "gem_red",
                                  "count": 1}]}],
             monsters=[])
    c._apply_scan("1", [], items=[{"name": "红宝石", "count": 2},
                                  {"name": "红血瓶", "count": 3}], grid={})
    items = c._map_history[0]["items"]
    by_name = {i["name"]: i for i in items}
    assert by_name["红宝石"]["count"] == 2     # 按图标身份归一，数量更新
    assert "红血瓶" in by_name                  # 新资源追加


# ---- 刷新任务的整条路：截图读不出来 / 模型没认出 / 认出来了 ----

class ScanFake(Fake):
    """把线程和"排回界面线程"都改成同步跑，好断言结果。"""

    def __init__(self, history, monsters=None):
        super().__init__(history, monsters)
        self.thread = None
        self.tasks = []

    def _start_thread(self, run):
        self.thread = run

    def _post(self, call):
        call()

    def _set_task(self, task_id, **fields):
        self.tasks.append((task_id, fields))


def _asset(name):
    """仓库里现成的一张图（测试里不写文件，直接借 assets）。"""
    import os
    import chaita
    root = os.path.dirname(os.path.dirname(os.path.abspath(chaita.__file__)))
    return os.path.join(root, "assets", "items", name)


def _run_scan(monkeypatch, image_url, read_floor_map=None):
    import chaita.game.read as game_read
    if read_floor_map is not None:
        monkeypatch.setattr(game_read, "read_floor_map", read_floor_map)
    c = ScanFake(history=[{"floor": "1", "mons": [], "items": [],
                           "grid": {"cells": []}}],
                 monsters=[{"name": "血蚊"}])
    c._start_scan_task(image_url, "1", task_id=7)
    c.thread()                                  # 同步跑一遍"后台"
    return c


def test_scan_task_reports_unreadable_screenshot(monkeypatch):
    _quiet(monkeypatch)
    c = _run_scan(monkeypatch, "file:///根本没有这个文件.png")

    assert c.tasks[-1] == (7, {"state": "failed",
                               "text": "统计失败：截图读不出来"})
    assert c._counting_floor == ""              # 收尾要把"正在统计"清掉


def test_scan_task_reports_non_image_file(monkeypatch):
    _quiet(monkeypatch)
    import os
    c = _run_scan(monkeypatch, os.path.join(os.path.dirname(_asset("x")),
                                            "..", "..", "pytest.ini"))

    assert c.tasks[-1][1]["text"] == "统计失败：截图读不出来"


def test_scan_task_reports_model_failure(monkeypatch):
    _quiet(monkeypatch)
    png = _asset("gem_red.png")

    def boom(*args, **kwargs):
        raise RuntimeError("模型挂了")

    c = _run_scan(monkeypatch, png, read_floor_map=boom)

    assert c.tasks[-1][1]["text"] == "统计失败：没认出怪和资源"


def test_scan_task_applies_what_it_read(monkeypatch):
    _quiet(monkeypatch)
    png = _asset("gem_red.png")

    data = {"mons": [{"name": "血蚊", "count": 2}],
            "items": [{"name": "红宝石", "count": 1}],
            "grid": {"cells": []}}

    c = _run_scan(monkeypatch, png, read_floor_map=lambda *a, **k: data)

    assert c._map_history[0]["mons"] == [{"name": "血蚊", "count": 2}]
    assert c._map_history[0]["items"][0]["name"] == "红宝石"
    text = c.tasks[-1][1]["text"]
    assert text.startswith("1：1 种怪（新增 1）")
    assert "1 种资源（新增 1）" in text


def test_apply_scan_mentions_dropped_names_in_task(monkeypatch):
    _quiet(monkeypatch)
    c = ScanFake(history=[{"floor": "1", "mons": [], "items": []}],
                 monsters=[{"name": "红色史莱姆"}])
    c._apply_scan("1", [{"name": "绿头怪", "count": 3}], task_id=7,
                  items=[], grid={})

    text = c.tasks[-1][1]["text"]
    assert "忽略 1 个对不上手册的名字" in text


def test_apply_scan_reports_missing_floor(monkeypatch):
    _quiet(monkeypatch)
    c = ScanFake(history=[{"floor": "2", "mons": [], "items": []}])
    c._apply_scan("1", [{"name": "血蚊", "count": 1}], task_id=7)

    assert c.tasks[-1] == (7, {"state": "failed",
                               "text": "统计失败：这层不见了"})


def test_apply_scan_writes_aligned_grid(monkeypatch):
    _quiet(monkeypatch)
    c = ScanFake(history=[{"floor": "1", "mons": [], "items": [],
                           "grid": {"cells": []}}],
                 monsters=[{"name": "红色史莱姆"}])
    c._apply_scan("1", [], items=[],
                  grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                                   "name": "红史莱姆"}]})

    cells = c._map_history[0]["grid"]["cells"]
    # 走的是同一套名字归一：模型猜的简称被改成手册写法
    assert cells[0]["name"] == "红色史莱姆"

