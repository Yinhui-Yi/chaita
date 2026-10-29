"""手册读取落库单元测试（`chaita/ui/controller/reading/deliver.py`）。

真值来自规则：同名不覆盖、只补新怪、严格匹配别把大小蝙蝠并一只、
读到手后把地图上的旧缩写改成真名。
"""

from unittest.mock import Mock

from chaita.ui.controller.reading.deliver import ReadingDeliverMixin


class Fake(ReadingDeliverMixin):
    def __init__(self, monsters=None, history=None):
        self._monsters = [dict(m) for m in (monsters or [])]
        self._map_history = history or []
        self.monstersChanged = Mock()
        self.mapHistoryChanged = Mock()
        self._frame = 0
        self._chat_reply = ""
        self.chatReplyChanged = Mock()

    def _finish(self, *args, **kwargs):
        self._finished = args


class Result:
    def __init__(self, monsters):
        self.monsters = monsters


def test_deliver_monsters_appends_only_new():
    c = Fake([{"name": "血蚊", "hp": "999", "atk": "88"}])  # 用户改过的
    r = Result([
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skills": "", "count": None, "icon": None},
        {"name": "铁卫", "hp": "900", "atk": "40", "def": "10",
         "skills": "", "count": None, "icon": None},
    ])
    added, skipped = c._deliver_monsters(r)
    assert (added, skipped) == (1, 1)
    # 已有的血蚊不被手册覆盖
    assert c._monsters[0]["hp"] == "999"
    # 新怪补在末尾
    assert c._monsters[1]["name"] == "铁卫"


def test_deliver_monsters_strict_keeps_similar():
    # 严格模式：小蝙蝠 / 大蝙蝠共两个字，不能并成一只
    c = Fake([{"name": "小蝙蝠"}])
    r = Result([{"name": "大蝙蝠", "hp": "900", "skills": "", "icon": None}])
    added, skipped = c._deliver_monsters(r)
    assert (added, skipped) == (1, 0)
    assert [m["name"] for m in c._monsters] == ["小蝙蝠", "大蝙蝠"]


def test_deliver_monsters_aligns_floor_abbreviation():
    # 地图上已经有模型猜的缩写"红史莱姆"；手册读到真名"红色史莱姆"
    c = Fake([], history=[{"floor": "0层",
                           "mons": [{"name": "红史莱姆", "count": 2}]}])
    r = Result([{"name": "红色史莱姆", "hp": "1200", "skills": "", "icon": None}])
    added, skipped = c._deliver_monsters(r)
    assert added == 1
    assert [m["name"] for m in c._monsters] == ["红色史莱姆"]
    # 地图上的旧缩写被改成真名
    assert c._map_history[0]["mons"][0]["name"] == "红色史莱姆"


# ---- 手册读空的 / 有图标的 ----

def test_deliver_monsters_empty_reports():
    c = Fake()
    assert c._deliver_monsters(Result([])) is None
    assert c._finished[0] == "没读到怪物"


def test_deliver_monsters_saves_icon(monkeypatch):
    import chaita.ui.controller.reading.deliver as deliver_mod
    monkeypatch.setattr(deliver_mod, "_save_temp",
                        lambda image, name: "file:///mon_1.png")

    class Icon:
        size = 4

    c = Fake()
    r = Result([{"name": "血蚊", "hp": "1200", "skills": "",
                 "count": None, "icon": Icon()}])

    c._deliver_monsters(r)

    assert c._monsters[0]["icon"] == "file:///mon_1.png"
    assert "已记录 1 只怪物" in c._chat_reply


def test_deliver_monsters_all_skipped_says_so():
    c = Fake([{"name": "血蚊"}])
    r = Result([{"name": "血蚊", "hp": "1200", "skills": "", "icon": None}])

    c._deliver_monsters(r)

    assert c._chat_reply == "这 1 只都记过了，没动你改过的记录"


# ---- _deliver：一次读取的落库编排 ----

class Delivery(ReadingDeliverMixin):
    def __init__(self, monsters=None, history=None):
        self._monsters = [dict(m) for m in (monsters or [])]
        self._map_history = history or []
        self.monstersChanged = Mock()
        self.mapHistoryChanged = Mock()
        self.statusTextChanged = Mock()
        self.chatReplyChanged = Mock()
        self._frame = 0
        self._chat_reply = ""
        self._error_text = "旧的错误"
        self._tower_label = ""
        self._status_seq = -1
        self._last_status = {}
        self._last_tower = None
        self._status_locked = False
        self._cancelled = set()
        self.tasks = []
        self.stored = []
        self.applied_status = []

    def _set_task(self, task_id, **fields):
        self.tasks.append((task_id, fields))

    def _finish(self, *args, **kwargs):
        self.finished = (args, kwargs)

    def _apply_status(self, status):
        self.applied_status.append(status)

    def _store_map_entry(self, tower, result, entry_id, floor_text, here,
                         items=None, quick_map=None, grid=None):
        self.stored.append((floor_text, here, items, grid))


class MapResult:
    def __init__(self, kind="map", floor="3层", monsters=None, items=None,
                 grid=None, name="新新魔塔", status=None):
        self.kind = kind
        self.status = status if status is not None else {"floor": floor}
        self.monsters = monsters or []
        self.items = items or []
        self.grid = grid or {}
        self.name = name


class Tower:
    key = "h5mota"
    name = "h5mota 魔塔"


def test_deliver_cancelled_task_does_nothing():
    c = Delivery()
    c._cancelled = {7}
    c._deliver(Tower(), MapResult(), seq=1, task_id=7)
    assert c.stored == []
    assert c._error_text == "旧的错误"          # 连错误提示都不清


def test_deliver_monsters_kind_does_not_touch_map():
    c = Delivery()
    result = MapResult(kind="monsters",
                       monsters=[{"name": "血蚊", "hp": "1200",
                                  "skills": "", "icon": None},
                                 {"name": "铁卫", "hp": "900",
                                  "skills": "", "icon": None}])

    c._deliver(Tower(), result, task_id=7)

    assert c._monsters[0]["name"] == "血蚊"
    assert c.stored == []                       # 读手册不建地图层
    assert c.tasks[-1][1]["state"] == "done"
    assert c.tasks[-1][1]["text"].startswith("手册 2 只")


def test_deliver_parse_error_finishes():
    c = Delivery()
    result = MapResult(status={"_error": "坏 JSON", "_raw": "乱七八糟"})

    c._deliver(Tower(), result, task_id=7)

    assert c.finished[0][0] == "模型输出无法解析"
    assert c.stored == []


def test_deliver_map_mode_only_updates_tower_label():
    c = Delivery()
    c._last_status = {"hp": "1000"}

    c._deliver(Tower(), MapResult(), mode="map", seq=5)

    assert c._tower_label == "新新魔塔"
    assert c._last_status == {"hp": "1000"}     # 读地图不动人物面板


def test_deliver_older_seq_skips_status():
    c = Delivery()
    c._status_seq = 9
    c._last_status = {"hp": "1000"}

    c._deliver(Tower(), MapResult(status={"floor": "3层", "hp": "842"}), seq=1)

    assert c._last_status == {"hp": "1000"}     # 序号更旧的那次不许写
    assert c.stored, "地图记录还是要落的"


def test_deliver_status_lock_keeps_panel():
    c = Delivery()
    c._status_locked = True

    c._deliver(Tower(), MapResult(status={"floor": "3层", "hp": "842"}), seq=1)

    assert c.applied_status == []
    assert c._last_status == {}


def test_deliver_without_floor_does_not_store():
    c = Delivery()
    c._deliver(Tower(), MapResult(status={"floor": ""}), task_id=7)

    assert c.stored == []
    assert c.tasks[-1][1]["state"] == "failed"
    assert c.tasks[-1][1]["text"] == "没读出层数"
    assert "没读出层数" in c._chat_reply


def test_deliver_stores_entry_and_marks_task_running():
    c = Delivery()
    result = MapResult(monsters=[{"name": "血蚊", "count": 2}],
                       items=[{"name": "红宝石"}], grid={"cells": []})

    c._deliver(Tower(), result, task_id=7, seq=1)

    floor_text, here, items, grid = c.stored[0]
    assert floor_text == "3层"
    assert here == [{"name": "血蚊", "count": 2}]
    assert items == [{"name": "红宝石"}]
    assert c.tasks[-1][1] == {"state": "running", "text": "3层"}


def test_deliver_drops_unmatched_monster_names():
    c = Delivery(monsters=[{"name": "红色史莱姆"}])

    c._deliver(Tower(), MapResult(monsters=[{"name": "绿头怪", "count": 1}]))

    assert c.stored[0][1] == []                 # 对不上手册的名字不进记录


def test_deliver_treats_bad_count_as_unknown():
    c = Delivery()
    result = MapResult(monsters=[{"name": "血蚊", "count": "两只"},
                                 {"name": "铁卫", "count": 0},
                                 {"name": "小蝙蝠", "count": True}])

    c._deliver(Tower(), result)

    assert [row["count"] for row in c.stored[0][1]] == [None, None, None]


# ---- _apply_floor：层数一读出来先建条目 ----

def test_apply_floor_creates_entry_with_saved_shot(monkeypatch):
    import chaita.ui.controller.reading.deliver as deliver_mod
    monkeypatch.setattr(deliver_mod, "_save_temp",
                        lambda image, name: "file:///map.png")
    c = Delivery()
    c._set_task = lambda task_id, **fields: c.tasks.append((task_id, fields))

    c._apply_floor(Tower(), "3层", "IMG", task_id=7)

    assert c._map_history[0]["floor"] == "3层"
    assert c._map_history[0]["url"] == "file:///map.png"
    assert c._map_history[0]["mons"] == []


def test_apply_floor_keeps_existing_url(monkeypatch):
    import chaita.ui.controller.reading.deliver as deliver_mod
    monkeypatch.setattr(deliver_mod, "_save_temp",
                        lambda image, name: "不该被用到")
    c = Delivery(history=[{"floor": "3层", "url": "file:///old.png",
                           "mons": [], "items": []}])
    c._set_task = lambda task_id, **fields: None

    c._apply_floor(Tower(), "3层", "IMG")

    assert c._map_history[0]["url"] == "file:///old.png"


def test_apply_floor_ignores_cancelled_and_blank(monkeypatch):
    c = Delivery()
    c._set_task = lambda task_id, **fields: None
    c._cancelled = {7}

    c._apply_floor(Tower(), "3层", None, task_id=7)
    c._apply_floor(Tower(), "  ", None)

    assert c._map_history == []


def test_deliver_monsters_skips_matching_by_substring(monkeypatch):
    """手册页上印着真名：只认一模一样/缩写，不走"最像的那个"。"""
    c = Fake([{"name": "小蝙蝠"}])
    r = Result([{"name": "大蝙蝠", "hp": "", "skills": "", "icon": None}])
    added, skipped = c._deliver_monsters(r)
    assert (added, skipped) == (1, 0)
