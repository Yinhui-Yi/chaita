"""伤害计算单元测试（`chaita/game/battle.py`）。

规则口径（`battle.py` 文档里写的、对着 xinxin2/xinxin 引擎核过的公式）：
    每回合打   = max(1, 攻击 - 怪防御)
    打不动     = 攻击 < 怪防御
    每回合挨打 = max(1, 怪攻击 - 防御) × 连击次数   （攻击低过防御才是 0）
    回合数     = ceil(怪血量 / 每回合打)
    掉血       = (回合数 - 1) × 每回合挨打 + 一次性伤害（破甲/固伤/吸血/先攻）

每个期望值都按上面这条规则**手推**，不许调 `run_plan` / `fight` 当标准答案。
"""

from chaita.game import battle


# 注意：下面这些英雄的 **护盾(mdef) 一律 0** —— 护盾是"整场减一次"的规则（按教程塔），
# 开着它会把每条公式的期望值整体挪掉 20 点，反而看不出公式本身对不对。
# 护盾有自己的一组测试（`test_fight_shield_*`）。
HERO = {"hp": 1200, "atk": 60, "def": 30, "mdef": 0}
# 算多技能叠加时用血极厚的英雄，免得算到一半被血条截断
RICH = {"hp": 10 ** 9, "atk": 60, "def": 30, "mdef": 0}


# ---------- 数字解析 ----------

def test_parse_amount():
    assert battle.parse_amount("1200") == 1200
    assert battle.parse_amount("21000万") == 210000000
    assert battle.parse_amount("1.2亿") == 120000000
    assert battle.parse_amount("1,200") == 1200
    assert battle.parse_amount("") == 0
    assert battle.parse_amount(None) == 0
    assert battle.parse_amount(35) == 35


def test_parse_item_effect():
    assert battle.parse_item_effect("攻击力 +2") == {"atk": 2}
    assert battle.parse_item_effect("体力 +150") == {"hp": 150}
    assert battle.parse_item_effect("生命 +1000 · 攻击 +6 · 防御 +6 · 魔防 +10") == {
        "hp": 1000, "atk": 6, "def": 6, "mdef": 10}
    assert battle.parse_item_effect("敏捷 +1") == {}
    assert battle.parse_item_effect("") == {}


# ---------- 单只怪 ----------

def test_basic_fight():
    # 60 攻 - 20 防 = 40/回合；1200 / 40 = 30 回合；
    # 它倒下那回合不还手 → 挨 29 下 × (60-30)=30 = 870
    r = battle.fight(HERO, {"name": "血蚊", "hp": 1200, "atk": 60, "def": 20})
    assert r["ok"]
    assert r["atk_damage"] == 40
    assert r["turns"] == 30
    assert r["mon_damage"] == 30
    assert r["damage"] == 29 * 30
    assert r["hero_hp_after"] == 1200 - 870
    assert not r["lethal"]


def test_one_round_kill_costs_nothing():
    # 一刀秒（50 血 / 60 攻 = 1 回合）：它没机会还手 → 0
    r = battle.fight(HERO, {"name": "软泥", "hp": 50, "atk": 999, "def": 0})
    assert r["turns"] == 1
    assert r["damage"] == 0


def test_equal_defense_still_lands_one():
    # 攻防相等还是 1 点（引擎 `def-临界 <= atk <= def → 1`）
    r = battle.fight(HERO, {"name": "硬皮", "hp": 100, "atk": 30, "def": 0})
    assert r["mon_damage"] == 1
    # 100 血 / 60 攻 = 2 回合，它只在第 1 回合还手 → 1
    assert r["damage"] == 1


def test_zero_damage_when_defense_higher():
    # 怪攻 29 < 我防 30 → 0（不是 1）
    r = battle.fight(HERO, {"name": "弱鸡", "hp": 100, "atk": 29, "def": 0})
    assert r["mon_damage"] == 0
    assert r["damage"] == 0


def test_cannot_break_defense():
    # 攻击低于怪防御才是打不动
    r = battle.fight(HERO, {"name": "铁怪", "hp": 50, "atk": 1, "def": 999})
    assert not r["ok"]
    assert r["damage"] is None
    assert "打不动" in r["reason"]
    # 攻防正好相等是能打的（一次 1 点）
    eq = battle.fight(HERO, {"name": "铁怪", "hp": 50, "atk": 1, "def": 60})
    assert eq["ok"]
    assert eq["atk_damage"] == 1


# ---------- 技能 ----------

def test_double_attack():
    plain = battle.fight(RICH, {"name": "A", "hp": 1200, "atk": 60, "def": 20})
    double = battle.fight(RICH, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                          [{"name": "连击", "params": {}}])
    assert double["damage"] == plain["damage"] * 2
    assert any("挨 2 下" in n for n in double["notes"])


def test_triple_beats_double():
    r = battle.fight(RICH, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                     [{"name": "连击"}, {"name": "3连击"}])
    assert r["damage"] == 30 * 3 * 29


def test_first_strike():
    plain = battle.fight(HERO, {"name": "A", "hp": 1200, "atk": 60, "def": 20})
    first = battle.fight(HERO, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                         [{"name": "先攻"}])
    assert first["damage"] == plain["damage"] + 30


def test_armor_break_uses_params():
    r = battle.fight(HERO, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                     [{"name": "破甲", "params": {"defValue": "50"}}])
    # 破甲 = 防 30 × 50% = 15，加在 29 回合 × 30 = 870 上
    assert r["damage"] == 870 + 15
    none = battle.fight(HERO, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                        [{"name": "破甲", "params": {"defValue": "0"}}])
    assert none["damage"] == 870


def test_solid_is_fightable_but_lethal():
    # 坚固把怪防御顶到你的攻击 → 每次只打 1 点，回合数 = 它的血
    r = battle.fight(HERO, {"name": "A", "hp": 1200, "atk": 60, "def": 0},
                     [{"name": "坚固"}])
    assert r["ok"]
    assert r["atk_damage"] == 1
    assert r["turns"] == 1200
    assert r["lethal"]
    # 它真实要 1199 回合 × 30 = 35970，你只有 1200
    assert r["damage"] == 1199 * 30
    assert r["hero_hp_after"] == 0


def test_mimic():
    r = battle.fight(HERO, {"name": "A", "hp": 100, "atk": 0, "def": 0},
                     [{"name": "模仿"}])
    assert r["atk_damage"] == 30
    assert r["mon_damage"] == 30
    assert r["turns"] == 4
    assert r["damage"] == 3 * 30


def test_magic_ignores_defense():
    r = battle.fight(RICH, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                     [{"name": "魔攻", "code": "2"}])
    assert r["mon_damage"] == 60
    assert r["damage"] == 60 * 29


def test_vampire_open_drains_before_battle():
    tank = {"hp": 100000, "atk": 60, "def": 30, "mdef": 0}
    vamp = battle.fight(tank, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                        [{"name": "吸血", "code": "11",
                          "params": {"value": "50"}}])
    # 开打先吸 100000 × 50% = 50000，它回这么多血 → 回合数 = (1200+50000)/40
    import math
    assert vamp["turns"] == math.ceil((1200 + 50000) / 40)
    assert vamp["damage"] == 50000 + (math.ceil((1200 + 50000) / 40) - 1) * 30


def test_fixed_once():
    r = battle.fight(HERO, {"name": "A", "hp": 1200, "atk": 0, "def": 20},
                     [{"name": "固伤", "code": "22", "params": {"damage": "10"}}])
    assert r["damage"] == 10


def test_counter_and_fixed_together():
    r = battle.fight(RICH, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                     [{"name": "2连击", "code": "4"},
                      {"name": "反击", "code": "8", "params": {"atkValue": "50"}},
                      {"name": "固伤", "code": "22", "params": {"damage": "5"}}])
    # 每回合：(60-30) × 2 下 + 攻击 60 × 50% = 90；29 回合 + 固伤 5
    assert r["mon_damage"] == 60
    assert r["damage"] == 5 + 90 * 29


def test_self_destruct():
    r = battle.fight(HERO, {"name": "A", "hp": 100, "atk": 0, "def": 0},
                     [{"name": "自爆", "code": "19"}])
    assert r["damage"] == HERO["hp"] - 1


def test_lethal_does_not_cap_damage():
    # 打不过：真实要 870（29 回合 × 30），不是只截到你剩下的 100
    weak = {"hp": 100, "atk": 60, "def": 30, "mdef": 0}
    r = battle.fight(weak, {"name": "A", "hp": 1200, "atk": 60, "def": 20})
    assert r["lethal"]
    assert r["damage"] == 870
    assert r["hero_hp_after"] == 0


def test_no_fight():
    r = battle.fight(HERO, {"name": "A", "hp": 10, "atk": 10, "def": 0},
                     [{"name": "无法战斗"}])
    assert not r["ok"]
    assert "打不了" in r["reason"]


def test_unhandled_skills_are_reported_not_guessed():
    r = battle.fight(HERO, {"name": "A", "hp": 1200, "atk": 60, "def": 20},
                     [{"name": "领域", "params": {"value": "50"}},
                      {"name": "纳魔为攻"}])
    assert r["damage"] == 870
    joined = " ".join(r["unhandled"])
    assert "领域" in joined
    assert "纳魔为攻" in joined


# ---------- 一串东西 ----------

def plan():
    return [
        {"kind": "monster", "name": "血蚊", "hp": 1200, "atk": 60, "def": 20},
        {"kind": "item", "name": "红宝石", "effect": "攻击力 +2"},
        {"kind": "item", "name": "红血瓶", "effect": "体力 +150"},
        {"kind": "monster", "name": "铁卫", "hp": 900, "atk": 40, "def": 10},
    ]


def test_rows_in_order_with_running_hp():
    r = battle.run_plan(HERO, plan())
    rows = r["rows"]
    assert [row["name"] for row in rows] == ["血蚊", "红宝石", "红血瓶", "铁卫"]
    assert rows[0]["damage"] == 870
    assert rows[0]["hp_after"] == 330
    assert rows[1]["gains"] == {"atk": 2}
    assert rows[1]["stats"]["atk"] == 62
    assert rows[2]["hp_after"] == 480
    # 吃宝石后攻击 62：铁卫 900 血 / (62-10)=52 → 18 回合，挨 17 下 × (40-30)=10
    assert rows[3]["atk_damage"] == 52
    assert rows[3]["turns"] == 18
    assert rows[3]["damage"] == 17 * 10
    assert r["total_damage"] == 870 + 170
    assert r["hp_after"] == 480 - 170
    assert r["dead_at"] == -1


def test_item_before_monster_changes_damage():
    steps = plan()
    before = battle.run_plan(HERO, [steps[3]])["rows"][0]["damage"]
    after = battle.run_plan(HERO, plan())["rows"][3]["damage"]
    assert before == 170
    assert after == 170


def test_stops_at_death():
    steps = [
        {"kind": "monster", "name": "先死", "hp": 1200, "atk": 60, "def": 20},
        {"kind": "monster", "name": "补刀", "hp": 1200, "atk": 60, "def": 20},
    ]
    r = battle.run_plan({"hp": 120, "atk": 60, "def": 30, "mdef": 0}, steps)
    assert r["dead_at"] == 0
    assert len(r["rows"]) == 2
    assert r["rows"][1]["damage"] == 0
    assert not r["rows"][1]["ok"]
    assert "前面就打不过了" in r["rows"][1]["reason"]
    assert r["hp_after"] == 0


def test_unhandled_collected():
    steps = [{"kind": "monster", "name": "A", "hp": 100, "atk": 10, "def": 0,
              "skills": [{"name": "领域"}]},
             {"kind": "monster", "name": "B", "hp": 100, "atk": 10, "def": 0,
              "skills": [{"name": "领域"}, {"name": "疲劳"}]}]
    r = battle.run_plan(HERO, steps)
    joined = " ".join(r["unhandled"])
    assert "领域" in joined
    assert "疲劳" in joined
    assert len(r["unhandled"]) == 2


def test_count_repeats_the_step():
    steps = [
        {"kind": "monster", "name": "血蚊", "hp": 1200, "atk": 60, "def": 20,
         "count": 3},
        {"kind": "item", "name": "红宝石", "effect": "攻击力 +2", "count": 2},
        {"kind": "monster", "name": "铁卫", "hp": 900, "atk": 40, "def": 10},
    ]
    r = battle.run_plan(HERO, steps)
    rows = r["rows"]
    assert rows[0]["turns"] == 30 * 3
    assert rows[0]["damage"] == 870 * 3
    assert rows[1]["stats"]["atk"] == 60 + 2 * 2
    assert rows[2]["atk_damage"] == 64 - 10
    assert battle.step_count({"count": ""}) == 1
    assert battle.step_count({"count": "0"}) == 1


def test_killed_late_monster_shows_its_real_damage():
    # 用户："最后一个史莱姆怎么可能只掉 81 血？总掉血计算也错"。
    # 打不过的怪不能把伤害改成"你剩下的血"，要显示它真实要的血。
    steps = [
        {"kind": "monster", "name": "绿史莱姆", "hp": 100, "atk": 25, "def": 5},
        {"kind": "item", "name": "红宝石", "effect": "攻击力 +1"},
        {"kind": "monster", "name": "绿史莱姆", "hp": 100, "atk": 25, "def": 5},
        {"kind": "monster", "name": "红史莱姆", "hp": 120, "atk": 28, "def": 6},
        {"kind": "item", "name": "红宝石", "effect": "攻击力 +1"},
        {"kind": "item", "name": "红宝石", "effect": "攻击力 +1"},
        {"kind": "monster", "name": "绿史莱姆", "hp": 100, "atk": 25, "def": 5},
        {"kind": "item", "name": "蓝宝石", "effect": "防御力 +1"},
        {"kind": "monster", "name": "红史莱姆", "hp": 120, "atk": 28, "def": 6},
        {"kind": "item", "name": "蓝宝石", "effect": "防御力 +1"},
        {"kind": "item", "name": "蓝宝石", "effect": "防御力 +1"},
    ]
    r = battle.run_plan({"hp": 600, "atk": 12, "def": 16, "mdef": 0}, steps)
    monsters = [row for row in r["rows"] if row["kind"] == "monster"]
    assert [row["damage"] for row in monsters] == [126, 108, 204, 81, 143]
    assert monsters[-1]["lethal"]
    assert r["total_damage"] == 126 + 108 + 204 + 81 + 143
    assert r["dead_at"] == 8
    assert r["hp_after"] == 0


# ---------- fight 的各技能分支（traits 直接给 dict，逐条手推） ----------

H = {"hp": 100, "atk": 50, "def": 20, "mdef": 0}
M = {"hp": 100, "atk": 30, "def": 10}
# 基线：每回合打 40，挨 10，回合数 ceil(100/40)=3，掉血 2×10=20


def test_fight_no_fight_skill():
    r = battle.fight(H, M, {"no_fight": True})
    assert r["ok"] is False
    assert r["reason"] == "打不了"


def test_fight_no_damage_skill():
    r = battle.fight(H, M, {"no_damage": True})
    assert r["ok"] is True
    assert r["damage"] == 0


def test_fight_cant_break_defense():
    r = battle.fight({"hp": 100, "atk": 5, "def": 10, "mdef": 0},
                     {"hp": 100, "atk": 10, "def": 50}, None)
    assert r["ok"] is False
    assert r["reason"] == "打不动"


def test_fight_multi_hit():
    r = battle.fight(H, M, {"hits": 2})
    assert r["damage"] == 40       # 每回合挨 20，2 回合


def test_fight_first_strike():
    r = battle.fight(H, M, {"first_strike": True})
    assert r["damage"] == 30       # 先攻 +10，再 2 回合 ×10


def test_fight_armor_break():
    r = battle.fight(H, M, {"armor_break": 50})
    assert r["damage"] == 30       # 破甲 +10（20 防 ×50%），再 20


def test_fight_vampire_open():
    r = battle.fight(H, M, {"vampire_open": 50})
    # 吸血先掉 50、怪回 50 → 怪 150 血，回合数 4，挨 3 下
    assert r["damage"] == 50 + 3 * 10
    assert r["hero_hp_after"] == 20


def test_fight_self_destruct():
    r = battle.fight(H, M, {"self_destruct": True})
    assert r["damage"] == 99       # 自爆：打完血只剩 1
    assert r["hero_hp_after"] == 1


def test_fight_counter():
    r = battle.fight(H, M, {"counter": 100})
    # 反击：每回合额外挨 50（你攻 50 ×100%），每回合 60，2 回合 → 120
    assert r["damage"] == 120
    assert r["lethal"] is True


def test_fight_ignore_defense():
    r = battle.fight(H, M, {"ignore_def": True})
    assert r["damage"] == 60       # 挨打不看防御：每回合 30，2 回合


def test_fight_mimic():
    r = battle.fight(H, M, {"mimic": True})
    # 怪复制你的攻 50 防 20：你每回合打 30，挨 30，回合数 4，挨 3 下
    assert r["damage"] == 90


# ---------- 护盾（魔防）：整场减一次，按教程塔 ----------
# xinxin/project/functions.js:1779
#     var damage = init_damage + expectedDamage; damage -= hero_mdef;
# 之后才加仇恨/固伤 —— 那两项不吃护盾减免。

def test_fight_shield_subtracts_once_from_the_whole_battle():
    # 一格 M：怪 100 血 30 攻 0 防，你 50 攻 → 2 回合，它倒那回合不还手 → 原本掉 20
    # 护盾 5 只减一次 → 20 - 5 = 15（不是每回合都减）
    hero = {"hp": 100, "atk": 50, "def": 20, "mdef": 5}
    r = battle.fight(hero, M, {})
    assert r["damage"] == 15
    assert any("护盾：-5" in note for note in r["notes"])


def test_fight_shield_never_makes_damage_negative():
    # 护盾 40 > 这一场要掉的 20：减到 0 就停，而且把"还剩多少"说出来
    hero = {"hp": 100, "atk": 50, "def": 20, "mdef": 40}
    r = battle.fight(hero, M, {})
    assert r["damage"] == 0
    assert any("还剩 20" in note for note in r["notes"])
    assert r["hero_hp_after"] == 100


def test_fight_shield_does_not_reduce_fixed_damage():
    # 固伤 7（护盾不减）+ 原本掉 20 - 护盾 5 = 15，合计 22
    hero = {"hp": 100, "atk": 50, "def": 20, "mdef": 5}
    r = battle.fight(hero, M, {"fixed_once": 7})
    assert r["damage"] == 22


def test_fight_zero_shield_changes_nothing():
    r = battle.fight({"hp": 100, "atk": 50, "def": 20, "mdef": 0}, M, {})
    assert r["damage"] == 20
    assert not any("护盾" in note for note in r["notes"])


def test_run_plan_applies_shield_per_battle():
    # 每场各减一次护盾 5：这两只怪 0 防 → 一刀两回合，每场原本掉 10，减完 5，合计 10
    hero = {"hp": 500, "atk": 50, "def": 20, "mdef": 5}
    steps = [{"kind": "monster", "name": "M", "hp": 100, "atk": 30, "def": 0},
             {"kind": "monster", "name": "M", "hp": 100, "atk": 30, "def": 0}]
    r = battle.run_plan(hero, steps)
    assert [row["damage"] for row in r["rows"]] == [5, 5]
    assert r["total_damage"] == 10
