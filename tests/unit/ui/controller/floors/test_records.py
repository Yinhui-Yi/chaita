"""records 的备忘/删层/资源显示单元测试（`chaita/ui/controller/floors/records.py`）。

真值来自规则：备忘可写可清、删层只删这一条、资源图标/效果以道具表为准。
"""

from unittest.mock import Mock

from chaita.ui.controller.floors.records import RecordsMixin


class FakeRecords(RecordsMixin):
    def __init__(self, history):
        self._map_history = history
        self.mapHistoryChanged = Mock()
        self._monsters = []


def test_save_floor_memo():
    c = FakeRecords([{"floor": "1层"}])
    c.saveFloorMemo("1层", "记得拿宝石")
    assert c._map_history[0]["memo"] == "记得拿宝石"
    # 清空 = 删掉这个字段
    c.saveFloorMemo("1层", "")
    assert "memo" not in c._map_history[0]
    # 不存在的层不崩、不动
    c.saveFloorMemo("没有", "x")
    assert len(c._map_history) == 1


def test_remove_floor():
    c = FakeRecords([{"floor": "1层"}, {"floor": "2层"}])
    c.removeFloor("1层")
    assert [e["floor"] for e in c._map_history] == ["2层"]


def test_fill_item_display():
    # 图标和效果都按道具表补
    gem = c_fill_item({"name": "红宝石"})
    assert gem["icon"] == "gem_red"
    assert gem["effect"] == "攻击力 +1"

    potion = c_fill_item({"name": "红血瓶"})
    assert potion["icon"] == "potion_red"
    assert potion["effect"] == "体力 +150"


def test_fill_item_display_keeps_manual_effect():
    # 用户自己改过的数值（effect_manual）不许被道具表盖回去
    item = c_fill_item({"name": "红宝石", "effect": "攻击力 +9",
                        "effect_manual": True})
    assert item["effect"] == "攻击力 +9"


def test_floor_history_is_not_capped():
    """层记录**不设上限**：一千层的塔读满 1000 层也不许把早层删掉。

    用户 2026-10-31："我1000层魔塔怎么办" —— 以前 `MAP_HISTORY_LIMIT = 30`，
    读满 30 层就把最早那条整条删掉（地图/怪/资源/路线/楼梯一起没）。
    """
    history = [{"floor": "通天塔%d" % n} for n in range(1, 41)]
    c = FakeRecords(history)
    # 建一条新层（读不到图时会走这里），老的 40 层必须一条不少
    assert c.ensureFloor("通天塔41") is True
    assert len(c._map_history) == 41
    names = [entry["floor"] for entry in c._map_history]
    assert "通天塔1" in names and "通天塔41" in names
    # 已经有的层不重复建
    assert c.ensureFloor("通天塔1") is False
    assert len(c._map_history) == 41


def c_fill_item(item):
    return FakeRecords([])._fill_item_display(item)
