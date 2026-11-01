"""controller 层 battle mixin 单元测试（`chaita/ui/controller/battle.py`）。

真值来自规则：状态读数解析、手册怪摊平、算一串交给 run_plan、
"加属性收益"怎么把各层剩下的怪分组算账。
"""

from chaita.ui.controller.battle import BattleMixin

import json


class FakeBattle(BattleMixin):
    def __init__(self, status=None, monsters=None, floors=None):
        self._last_status = status if isinstance(status, dict) else {}
        self._tower_label = "拆个魔塔"
        self._monsters = monsters or []
        self._map_history = floors or []


def test_battle_hero_parses_status():
    c = FakeBattle({"hp": "1,200", "atk": "60", "def": "30", "mdef": "20"})
    assert c.battleHero() == {"hp": 1200, "atk": 60, "def": 30, "mdef": 20,
                              "tower": "拆个魔塔"}


def test_battle_hero_empty_status_is_zero():
    c = FakeBattle()
    assert c.battleHero() == {"hp": 0, "atk": 0, "def": 0, "mdef": 0,
                              "tower": "拆个魔塔"}


def test_battle_monsters_flattens_skills():
    c = FakeBattle(monsters=[
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skills": "先攻", "skill_items": [{"name": "先攻", "code": "",
                                            "params": {}}]},
        {"name": "", "hp": "1", "atk": "1", "def": "1"},   # 空名跳过
    ])
    mons = c.battleMonsters()
    assert len(mons) == 1
    assert mons[0]["name"] == "血蚊"
    assert mons[0]["hp"] == 1200
    assert mons[0]["atk"] == 60
    assert mons[0]["skillsText"] == "先攻"
    assert mons[0]["skills"][0]["name"] == "先攻"


def test_compute_battle():
    c = FakeBattle()
    r = c.computeBattle(
        '{"hero":{"hp":1200,"atk":60,"def":30,"mdef":20},'
        '"steps":[{"kind":"monster","name":"血蚊","hp":1200,'
        '"atk":60,"def":20,"count":1,"skills":[]}]}')
    # 战斗本身掉 870（29 下 × 30），再减一次护盾 20 → 850
    assert r["total_damage"] == 850
    assert r["hp_after"] == 350


def test_compute_battle_bad_payload():
    c = FakeBattle()
    r = c.computeBattle("不是 json")
    assert r["total_damage"] == 0


# ---- 加属性收益：再加 X 点攻/防/魔防，剩下的怪少掉多少（按层分组） ----
#
# 真值**手算**（和集成测试同一份）：英雄 血 1000 / 攻 90 / 防 30；
# 血蚊 1200 血 / 攻 60 / 防 20 / 带先攻：
#   攻 90：每回合 90-20=70 → ceil(1200/70)=18 回合 → 17 下 ×30 + 先攻 30 = 540
#   攻 91：每回合 71 → ceil(1200/71)=17 → 16 下 ×30 + 30 = 510
#   → 每只少掉 30

HERO = {"hp": "1000", "atk": "90", "def": "30", "mdef": "0"}
HANDBOOK = [{"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
             "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]


def _floor(name, mons):
    return {"floor": name, "url": "", "items": [], "grid": {"cells": []},
            "mons": mons}


def _gain(floors, gain=None, cap=0):
    c = FakeBattle(status=HERO, monsters=HANDBOOK, floors=floors)
    return c.propertyGain(json.dumps({"gain": gain or {"atk": 1},
                                      "cap": cap}))


def test_property_gain_groups_the_remaining_monsters_by_floor():
    """测什么：两层各有剩怪 → 一层一组，每层各自的小计，合计是两层相加。"""
    r = _gain([_floor("1层", [{"name": "血蚊", "count": 2}]),
               _floor("2层", [{"name": "血蚊", "count": 1}])])
    assert [one["floor"] for one in r["floors"]] == ["1层", "2层"]
    assert [one["saved"] for one in r["floors"]] == [60, 30]
    assert r["floors"][0]["species"][0] == {"name": "血蚊", "count": 2,
                                          "one": 30, "all": 60}
    assert r["total_saved"] == 90
    assert r["count_species"] == 2 and r["count_monsters"] == 3


def test_property_gain_leaves_out_the_monsters_you_crossed_off():
    """测什么：划掉的（done）不算剩下；同层同名合并数量，没填数量当 1 只。"""
    r = _gain([_floor("1层", [{"name": "血蚊", "count": 1},
                              {"name": "血蚊", "count": 2},
                              {"name": "血蚊", "count": 9, "done": True},
                              {"name": "血蚊"}])])
    species = r["floors"][0]["species"]
    assert len(species) == 1, "同层同名应该并成一行"
    # 1 + 2 + 1（没填数量）= 4 只；划掉的 9 只不算
    assert species[0]["count"] == 4
    assert species[0]["all"] == 120
    assert r["total_saved"] == 120


def test_property_gain_lists_a_monster_the_handbook_does_not_know():
    """测什么：手册里没有数值的怪 → 列在这一层的 unknown 里、写明原因、不计入合计。"""
    r = _gain([_floor("1层", [{"name": "血蚊", "count": 1},
                              {"name": "鬼影", "count": 3}])])
    unknown = r["floors"][0]["unknown"]
    assert unknown == [{"name": "鬼影", "count": 3,
                        "reason": "手册里没有它的数值"}]
    # 只有血蚊进了合计（鬼影那 3 只绝不编数字）
    assert r["total_saved"] == 30
    assert r["count_monsters"] == 1


def test_property_gain_puts_the_upper_bound_on_the_total_only():
    """测什么：上界只封合计 —— 合计按上界算，每种那两列照实写。"""
    r = _gain([_floor("1层", [{"name": "血蚊", "count": 3}])], cap=20)
    assert r["total_saved"] == 90, "没封之前是 3 只 ×30"
    assert r["capped_saved"] == 20
    assert r["capped"] is True and r["cap"] == 20
    species = r["floors"][0]["species"][0]
    assert species["one"] == 30 and species["all"] == 90, "单只/单种不封"


def test_property_gain_reports_the_hero_values_it_used():
    """测什么：结果里带回"这次用的是哪一份属性"，界面照它显示不用再问一次。"""
    r = _gain([_floor("1层", [{"name": "血蚊", "count": 1}])])
    assert r["hero"] == {"hp": 1000, "atk": 90, "def": 30, "mdef": 0,
                         "tower": "拆个魔塔"}


def test_property_gain_without_any_floor_is_empty():
    """测什么：清单里没有剩下的怪 / 还没读楼层 → 空的，不炸。"""
    r = FakeBattle(status=HERO, monsters=HANDBOOK).propertyGain("{}")
    assert r["floors"] == []
    assert r["total_saved"] == 0 and r["count_monsters"] == 0
