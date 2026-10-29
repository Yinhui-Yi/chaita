"""读取落库集成测试：一次「读取」的结果走完 名字归一 → 层记录 → 状态面板。

这里用真 Controller + 真 `_deliver`（不是 fake mixin）：整条链是
`monster_names.align`（怪名归一）→ `texts._floor_text`（层名）→
`records._store_map_entry` + `floors.common._align_grid_names`（层记录 + 格子归一）
→ `status._apply_status`（状态面板）。期望值从规则手写，不拿 run_plan 自己比自己。
"""

from chaita.game import read as game_read
from chaita.game import towers

from .... import helpers


def test_deliver_read_aligns_monster_names_and_stores_floor():
    controller, engine, window = helpers.make_controller()
    # 手册里已经有真名"红色史莱姆"；图上模型猜的是缩写"红史莱姆"
    controller._monsters = [{"name": "红色史莱姆", "hp": "1200", "atk": "60",
                             "def": "20"}]
    result = game_read.Reading(
        status={"hp": "1000", "atk": "90", "def": "30", "mdef": "10",
                "floor": "1"},
        map=None, name="新新魔塔", kind="status",
        monsters=[{"name": "红史莱姆", "count": 2}],
        floor="1",
        items=[{"name": "红宝石", "effect": "攻击力 +1", "count": 1,
                "icon": "gem_red"}],
        grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                         "name": "红史莱姆"}]})
    controller._deliver(towers.H5_MOTA, result, seq=0)
    helpers.APP.processEvents()

    # 状态面板：按"谁序号最大"写入
    assert controller._last_status["hp"] == "1000"
    assert controller._tower_label == "新新魔塔"

    # 层记录：怪名归一到手册写法，缩写"红史莱姆"不该进记录
    entry = controller._map_history[0]
    assert entry["floor"] == "1"
    assert entry["mons"] == [{"name": "红色史莱姆", "count": 2}]
    assert entry["items"] == [{"name": "红宝石", "effect": "攻击力 +1",
                               "count": 1, "icon": "gem_red"}]
    # 路线链用的格子记录，怪名同样归一
    assert entry["grid"]["cells"][0]["name"] == "红色史莱姆"


def test_deliver_without_floor_does_not_store_entry():
    controller, engine, window = helpers.make_controller()
    result = game_read.Reading(
        status={"hp": "1000", "atk": "90"}, map=None, name="新新魔塔",
        kind="status", monsters=[], floor=None, items=[])
    controller._deliver(towers.H5_MOTA, result, seq=0)
    helpers.APP.processEvents()
    # 没读出层数：地图列表不记这一条
    assert controller._map_history == []
    assert "没读出层数" in controller._chat_reply
