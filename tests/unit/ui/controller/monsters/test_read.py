"""怪物读取列表单元测试（`chaita/ui/controller/monsters/read.py`）。

真值来自规则：技能只统计地图上加过的怪、同名技能一只只算一次、老 skills 串补齐成行。
"""

from chaita.ui.controller.monsters.read import ReadMixin


class FakeRead(ReadMixin):
    def __init__(self, monsters=None, history=None):
        self._monsters = monsters or []
        self._map_history = history or []
        self._monster_templates = []
        self._skill_catalog = ["先攻"]
        self._tower_label = ""


def test_map_monster_names_dedup_in_order():
    c = FakeRead(history=[
        {"mons": [{"name": "血蚊"}, {"name": "铁卫"}]},
        {"mons": [{"name": "血蚊"}, {"name": "史莱姆"}]},
    ])
    assert c._map_monster_names() == ["血蚊", "铁卫", "史莱姆"]


def test_get_monsters_fills_skill_items():
    c = FakeRead(monsters=[{"name": "血蚊", "skills": "先攻"}])
    out = c._get_monsters()
    assert out[0]["name"] == "血蚊"
    assert [s["name"] for s in out[0]["skill_items"]] == ["先攻"]


def test_skill_stats_only_map_monsters():
    c = FakeRead(
        monsters=[
            {"name": "血蚊",
             "skill_items": [{"name": "先攻", "value": "30", "code": "1",
                              "params": {}}]},
            {"name": "铁卫",
             "skill_items": [{"name": "破甲", "value": "50", "code": "7",
                              "params": {}}]},
        ],
        history=[{"mons": [{"name": "血蚊"}]}])
    stats = c._get_skill_stats()
    assert len(stats) == 1
    assert stats[0]["skill"] == "先攻"
    assert stats[0]["count"] == 1
    assert stats[0]["values"] == ["30"]
    assert stats[0]["mons"][0]["name"] == "血蚊"


def test_skill_stats_dedup_same_skill_per_monster():
    c = FakeRead(
        monsters=[{"name": "血蚊",
                   "skill_items": [{"name": "先攻", "value": "30", "code": "1",
                                    "params": {}},
                                   {"name": "先攻", "value": "40", "code": "1",
                                    "params": {}}]}],
        history=[{"mons": [{"name": "血蚊"}]}])
    stats = c._get_skill_stats()
    assert stats[0]["count"] == 1      # 同一只怪重复技能只算一次


def test_skill_catalog_keeps_unknown_tokens():
    c = FakeRead(monsters=[{"name": "怪", "skills": "新技能"}])
    out = c._get_skill_catalog()
    assert "先攻" in out
    assert "新技能" in out
