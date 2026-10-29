"""controller 层 battle mixin 单元测试（`chaita/ui/controller/battle.py`）。

真值来自规则：状态读数解析、手册怪摊平、算一串交给 run_plan。
"""

from chaita.ui.controller.battle import BattleMixin


class FakeBattle(BattleMixin):
    def __init__(self, status=None, monsters=None):
        self._last_status = status if isinstance(status, dict) else {}
        self._tower_label = "拆个魔塔"
        self._monsters = monsters or []


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
