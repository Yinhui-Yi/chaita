"""伤害计算：按魔塔的回合规则算"打这只怪掉多少血"。

用户："做一个伤害计算的功能：1.可以根据人物的当前状态计算掉血 2.给一连串东西
（怪、宝石、血），要给出打每个怪的掉血及最终掉血 3.要考虑技能、考虑多技能兼容"。

**不算图、不问模型**：这里只有公式。技能的语义取自塔自己的引擎
（`assets/skill_effects.json` 的 `code`，也就是 h5mota 的 special 编号），
数字用怪物编辑里填的参数（破甲 `defValue`、反击 `atkValue`、连击 `n`……）。

基础公式（每只怪单独算，逐回合走一遍）——
**数值口径对着两座塔的引擎源码核过**（用户："说了伤害不对，给我查"）：

    每回合打怪 = max(1, 攻击 - 怪防御)                    ← 攻防相等也打得动（1 点）
    打不动     = 攻击 < 怪防御                            ← 只有真低才打不动
    每回合挨打 = max(1, 怪攻击 - 防御)（低过防御才是 0）× 连击次数
    回合数     = ceil(怪血量 / 每回合打怪)
    掉血       = (回合数 - 1) × 每回合挨打 + 一次性伤害（破甲/固伤/吸血/先攻）

"它倒下的那一回合不再反击"和"最低 1 点"是引擎里的硬规则，不是近似：
  · `xinxin2/project/functions.js` 的 `getDamageInfo`：`core.heroAtk(...)` 之后
    `if (m.hp <= 0) break;` 才轮到 `core.monAtk(...)`；
  · `xinxin/project/functions.js`：`calculateFormulaExpectation()` 里
    期望回合数 = `M - 1`（M = ceil(血 / 每回合打)），
    `_calculateBaseDamage(atk, def, 临界)` 里 `def-临界 <= atk <= def → 1`（临界默认 0）；
  · `xinxin2/project/plugins.js`：`dmg = m.atk - h.def; if (dmg < -defm=40) 0;
    else if (dmg < 1) 1` —— 它同理。

"逐回合模拟"而不是套闭式公式：吸血、反击、固定伤害都会改变回合数，
一轮轮试最不容易算错。

**算不了的技能不假装算**：疲劳、光环、领域、必杀、秘术打公主……
一律列进 `unhandled`，界面上照实写"这些没算进去"（用户看得见才不会误判）。
"""

import math
import re

# ---- 数字：塔里的数值可能写成 "21000万" / "1.2亿" / "1,200" ----
_UNITS = {"万": 10 ** 4, "萬": 10 ** 4, "亿": 10 ** 8, "億": 10 ** 8,
          "千": 10 ** 3, "k": 10 ** 3, "K": 10 ** 3, "w": 10 ** 4,
          "W": 10 ** 4}
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")

# 一次战斗最多试这么多回合：数值离谱时别把界面卡死
MAX_TURNS = 200000


def parse_amount(value) -> int:
    """把界面/手册上的数写成整数："21000万" → 210000000，"1.2亿" → 120000000。"""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text:
        return 0
    found = _NUMBER.search(text)
    if not found:
        return 0
    number = float(found.group(0))
    tail = text[found.end():].strip()
    for unit, scale in _UNITS.items():
        if unit in tail:
            return int(round(number * scale))
    return int(round(number))


# ---- 技能：引擎 code（h5mota special）→ 战斗里怎么算 ----
# 名字兜底：塔里有些技能改了名字、或者编辑时是自己写的，按关键词也能认出来。
_CODE_NAMES = {
    "1": ("first_strike",),
    "29": ("first_strike",),
    "2": ("ignore_def",),
    "30": ("ignore_def",),
    "60": ("ignore_def", "triple_if_low"),
    "66": ("ignore_def", "heal_hit50"),
    "61": ("hits_princess",),
    "62": ("hits_princess",),
    "63": ("hits_princess",),
    "64": ("hits_princess",),
    "65": ("hits_princess", "heal_hit50"),
    "67": ("hits_princess", "heal_hit50"),
    "3": ("solid",),
    "31": ("solid",),
    "85": ("solid", "copy_atk"),
    "35": ("copy_atk",),
    "4": ("hits2",),
    "5": ("hits3",),
    "6": ("hits_n",),
    "87": ("hits6",),
    "7": ("armor_break",),
    "8": ("counter",),
    "9": ("shield",),
    "10": ("mimic",),
    "11": ("vampire_open",),
    "19": ("self_destruct",),
    "20": ("no_fight",),
    "21": ("degenerate",),
    "22": ("fixed_once",),
    "23": ("regen",),
    "34": ("regen",),
    "36": ("no_damage",),
    "55": ("target_princess",),
    "57": ("heal_hit50",),
    "84": ("fixed_hit",),
}

_NAME_KINDS = (
    ("先攻", "first_strike"),
    ("魔攻", "ignore_def"),
    ("无视防御", "ignore_def"),
    ("暗魔法", "ignore_def"),
    ("坚固", "solid"),
    ("变硬", "solid"),
    ("硬化", "solid"),
    ("模仿", "mimic"),
    ("3连击", "hits3"),
    ("2连击", "hits2"),
    ("二连击", "hits2"),
    ("连击", "hits2"),
    ("破甲", "armor_break"),
    ("反击", "counter"),
    ("吸血", "vampire_open"),
    ("自爆", "self_destruct"),
    ("无敌", "no_fight"),
    ("无法战斗", "no_fight"),
    ("退化", "degenerate"),
    ("固伤", "fixed_once"),
    ("固定伤害", "fixed_once"),
    ("狙击", "target_princess"),
)

# 这些技能算不了（或者影响的是走位/战后），要说出来而不是瞎算
_UNHANDLED_HINTS = (
    ("领域", "领域：站在范围内每走一步掉血，不在这场战斗里"),
    ("阻击", "阻击：走位时掉血，不在这场战斗里"),
    ("激光", "激光：同行同列走才掉血，不在这场战斗里"),
    ("夹击", "夹击：走到两只相同的怪中间才掉血，不在这场战斗里"),
    ("光环", "光环：会给别的怪加属性，这里只按这只怪自己的数值算"),
    ("支援", "支援：会叫来周围的怪一起打，公式没算"),
    ("捕捉", "捕捉：会强制开战，公式没算"),
    ("仇恨", "仇恨：伤害取决于之前攒的仇恨值，公式不知道你攒了多少"),
    ("疲劳", "疲劳：战斗里会掉疲劳度，公式没算"),
    ("虚弱", "虚弱：战后状态，公式没算"),
    ("衰弱", "衰弱：战后攻防会掉，公式没算"),
    ("中毒", "中毒：战后持续掉血，公式没算"),
    ("猛毒", "猛毒：会中毒并变强，公式没算"),
    ("诅咒", "诅咒：战后拿不到金币经验，公式没算"),
    ("必杀", "必杀：暴击概率与倍率要真打才知道，公式按普通伤害算"),
    ("会心", "必杀：暴击概率与倍率要真打才知道，公式按普通伤害算"),
    ("秘术", "秘术：会顺带打公主（魔防），这里只算你自己的掉血"),
    ("魔法攻击", "魔法攻击：会顺带打公主（魔防），这里只算你自己的掉血"),
    ("净化", "净化：打护盾，公式没算"),
    ("邪眼", "邪眼：影响道具使用，跟伤害无关"),
    ("重生", "重生：死了会变成别的怪，公式没算"),
    ("再生", "再生：被打会回血，公式没算"),
    ("退化", "退化：战后你的攻防会掉，这里只在结果里提醒"),
    ("催眠", "催眠：会让你打自己，公式没算"),
    ("破甲刃", "破甲刃：战后会削你的防御，公式没算"),
    ("超负荷", "超负荷：魔力弹跳伤害，公式没算"),
    ("BOSS", "BOSS 专属机制：塔自己改过，公式没算"),
    ("身体", "元素身体：战后地上有岩浆/冰，跟这场战斗的掉血无关"),
)


def _trait(name: str, code: str) -> list:
    """技能名/code → 行为列表（比如吸血 = vampire_open）。"""
    found = list(_CODE_NAMES.get(str(code or "").strip(), ()))
    if found:
        return found
    text = str(name or "").strip()
    for word, kind in _NAME_KINDS:
        if word in text:
            return [kind]
    return []


def _number(params, field: str, fallback: int = 0) -> int:
    """技能参数里的一个数（怪物编辑里填的）；没填就用默认值。"""
    if not isinstance(params, dict):
        return fallback
    value = params.get(field)
    if value is None or value == "":
        return fallback
    if isinstance(value, bool):
        return 1 if value else 0
    return parse_amount(value)


def _flag(params, field: str) -> bool:
    if not isinstance(params, dict):
        return False
    value = params.get(field)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "✓", "是")


def read_skills(items) -> dict:
    """把这一只怪的技能读成"战斗里要用的那几件事"。

    items: `[{"name": "破甲", "code": "7", "params": {"defValue": "50"}}, ...]`
    返回：
        `{"hits": 2, "armor_break": 50, "counter": 30, "vampire_open": 40, ...,
           "notes": ["破甲 50%：额外 45 点"], "unhandled": ["疲劳：…"], "names": [...]}`
    """
    out = {"notes": [], "unhandled": [], "names": [], "hits": 1,
           "armor_break": 0, "counter": 0, "vampire_open": 0,
           "vampire_open_add": False, "heal_hit": 0, "fixed_once": 0,
           "fixed_hit": 0, "degenerate": (0, 0)}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        params = item.get("params") or {}
        code = str(item.get("code") or "").strip()
        kinds = _trait(name, code)
        out["names"].append(name)
        if not kinds:
            out["unhandled"].append(name)
            continue
        for kind in kinds:
            if kind == "first_strike":
                out["first_strike"] = True
            elif kind == "ignore_def":
                out["ignore_def"] = True
            elif kind == "triple_if_low":
                out["triple_if_low"] = True
            elif kind == "solid":
                out["solid"] = True
            elif kind == "copy_atk":
                out["copy_atk"] = True
            elif kind == "mimic":
                out["mimic"] = True
            elif kind == "hits2":
                out["hits"] = max(out["hits"], 2)
            elif kind == "hits3":
                out["hits"] = max(out["hits"], 3)
            elif kind == "hits6":
                out["hits"] = max(out["hits"], 6)
            elif kind == "hits_n":
                out["hits"] = max(out["hits"], max(1, _number(params, "n", 2)))
            elif kind == "armor_break":
                out["armor_break"] = max(out["armor_break"],
                                         _number(params, "defValue", 100))
            elif kind == "counter":
                out["counter"] = max(out["counter"], _number(params, "atkValue", 100))
            elif kind == "vampire_open":
                out["vampire_open"] = max(out["vampire_open"],
                                          _number(params, "value", 100))
                out["vampire_open_add"] = _flag(params, "add")
            elif kind == "heal_hit50":
                out["heal_hit"] = max(out["heal_hit"], 50)
            elif kind == "heal_hit":
                out["heal_hit"] = max(out["heal_hit"], _number(params, "value", 50))
            elif kind == "fixed_once":
                out["fixed_once"] += max(0, _number(params, "damage", 0))
            elif kind == "fixed_hit":
                out["fixed_hit"] += 100
            elif kind == "self_destruct":
                out["self_destruct"] = True
            elif kind == "no_fight":
                out["no_fight"] = True
            elif kind == "no_damage":
                out["no_damage"] = True
            elif kind == "target_princess":
                out["target_princess"] = True
            elif kind == "degenerate":
                down_atk = _number(params, "atkValue", 0)
                down_def = _number(params, "defValue", 0)
                out["degenerate"] = (down_atk, down_def)
            elif kind in ("shield", "regen", "hits_princess"):
                out["unhandled"].append(name + "（战斗之外的机制）")
        if out["hits"] > 1 and "hits" not in out["notes"]:
            out["notes"].append("连击：每回合挨 %d 下" % out["hits"])
        if out["armor_break"]:
            out["notes"].append("破甲 %d%%：按你的防御额外吃伤害"
                                % out["armor_break"])
        if out["counter"]:
            out["notes"].append("反击 %d%%：每回合按你的攻击额外吃伤害"
                                % out["counter"])
        if out["vampire_open"]:
            out["notes"].append("吸血 %d%%：开打前先掉血，怪物还回血"
                                % out["vampire_open"])
        if out["heal_hit"]:
            out["notes"].append("%s：打你的伤害回 %d%% 给它自己"
                                % (name, out["heal_hit"]))
        if out["fixed_once"]:
            out["notes"].append("%s：开打前固定吃 %d 点"
                                % (name, out["fixed_once"]))
        if out.get("self_destruct"):
            out["notes"].append("%s：打赢之后血只剩 1" % name)
        if out.get("target_princess"):
            out["notes"].append("%s：它打的是公主，不算你的掉血" % name)
        if out["degenerate"] != (0, 0):
            out["notes"].append("%s：战后攻/防 -%d/-%d"
                                % (name, out["degenerate"][0],
                                   out["degenerate"][1]))
    # 认不出的技能名换成一句人话
    explained = []
    for item in out["unhandled"]:
        hint = ""
        for word, text in _UNHANDLED_HINTS:
            if word in item:
                hint = text
                break
        explained.append(hint or ("%s：公式没算这个技能" % item))
    out["unhandled"] = explained
    return out


def fight(hero, monster, skills=None) -> dict:
    """打一只怪：返回掉血/回合/每回合伤害，以及"算不了"的东西。

    hero:    `{"hp": 1200, "atk": 60, "def": 30, "mdef": 20}`（人物当前状态）
    monster: `{"name": "双头蛇", "hp": 5000, "atk": 120, "def": 40}`
    skills:  技能列表（`read_skills` 的输入）；也可以直接给 `read_skills` 的结果
    """
    hero_hp = max(0, parse_amount((hero or {}).get("hp")))
    hero_atk = max(0, parse_amount((hero or {}).get("atk")))
    hero_def = max(0, parse_amount((hero or {}).get("def")))
    hero_mdef = max(0, parse_amount((hero or {}).get("mdef")))

    mon = monster or {}
    mon_hp = max(0, parse_amount(mon.get("hp")))
    mon_atk = max(0, parse_amount(mon.get("atk")))
    mon_def = max(0, parse_amount(mon.get("def")))

    traits = skills if isinstance(skills, dict) else read_skills(skills)
    notes = list(traits.get("notes") or [])
    unhandled = list(traits.get("unhandled") or [])
    name = str(mon.get("name") or "")
    base = {"name": name, "damage": None, "turns": 0, "mon_damage": 0,
            "atk_damage": 0, "hero_hp_after": hero_hp, "lethal": False,
            "notes": notes, "unhandled": unhandled, "degenerate": (0, 0)}

    if traits.get("no_fight"):
        return dict(base, ok=False, reason="打不了",
                    notes=notes + ["这只怪写着不能战斗（无法战斗/无敌），打它不会掉血也不算赢"])
    if traits.get("no_damage"):
        return dict(base, ok=True, damage=0, reason="特殊战斗：这类怪按 0 伤害算")

    # 模仿 / 仿攻 / 硬化+：先改怪的攻防
    if traits.get("mimic"):
        mon_atk = hero_atk
        mon_def = hero_def
    if traits.get("solid") and hero_atk > mon_def:
        mon_def = hero_atk
    if traits.get("copy_atk"):
        mon_atk = max(mon_atk, hero_atk)

    # 连击 / 反击 / 固定伤害 / 无视防御
    hits = max(1, int(traits.get("hits") or 1))
    def_used = hero_mdef if traits.get("use_mdef") else hero_def
    if traits.get("ignore_def"):
        def_used = 0
    if traits.get("triple_if_low") and mon_atk >= hero_def:
        mon_atk *= 3
    # 它打你：引擎里"攻击正好等于防御"还是掉 1 点（不是 0），
    # 只有攻击低于防御才是 0（xinxin `_calculateBaseDamage`：def-临界 <= atk <= def → 1）
    per_hit = mon_atk - def_used
    if traits.get("ignore_def"):
        per_hit = mon_atk
    per_hit = 0 if per_hit < 0 else max(1, per_hit)
    per_round = per_hit * hits
    if traits.get("fixed_hit"):
        per_round += int(traits["fixed_hit"])

    # 你打它：攻击正好等于防御也打得动（一次 1 点），攻击低于防御才是打不动
    atk_damage = hero_atk - mon_def
    if atk_damage < 0:
        return dict(base, ok=False, mon_damage=per_round, atk_damage=0,
                    reason="打不动",
                    notes=notes + ["打不动：你的攻击 %d < 它的防御 %d"
                                   % (hero_atk, mon_def)])
    atk_damage = max(1, atk_damage)

    # 开打前的一次性伤害
    damage = 0
    extra_notes = []
    if traits.get("armor_break"):
        extra = int(hero_def * int(traits["armor_break"]) / 100)
        damage += extra
        extra_notes.append("破甲：+%d" % extra)
    if traits.get("fixed_once"):
        damage += int(traits["fixed_once"])
    if traits.get("vampire_open"):
        drained = int(hero_hp * int(traits["vampire_open"]) / 100)
        damage += drained
        mon_hp += drained
        extra_notes.append("吸血：先掉 %d，它还回这么多血" % drained)
    if traits.get("first_strike"):
        damage += per_round
        extra_notes.append("先攻：+%d" % per_round)
    if traits.get("target_princess"):
        damage = 0
        per_round = 0

    # 逐回合：吸血（每回合回血）/ 反击 都会改变回合数，只能一轮轮试。
    # **它倒下的那一回合不再反击** —— 两座塔的引擎都这样：
    #   xinxin2：heroAtk 之后 `if (m.hp <= 0) break;` 才轮到 monAtk；
    #   xinxin ：期望回合数是 M-1（`expectedTurns = ... - 1`），M = ceil(血/每回合打)。
    #
    # **不按"你剩余血"截断伤害**（用户："最后一个史莱姆怎么可能只掉 81 血"）：
    # 以前这里 damage >= hero_hp 就把 damage 改写成 hero_hp —— 于是"打不过"的怪
    # 只显示你剩下那点血，看不出它真实能打多少，总掉血也被截成血条。现在正常算完，
    # 它真实掉多少就是多少；打不打得过另由 `lethal` 说明。
    left = mon_hp
    turns = 0
    per_round_total = per_round
    if traits.get("counter"):
        per_round_total += int(hero_atk * int(traits["counter"]) / 100)
    while left > 0 and turns < MAX_TURNS:
        turns += 1
        left -= atk_damage
        if traits.get("heal_hit") and per_round_total:
            left = min(mon_hp, left + int(per_round_total * int(traits["heal_hit"]) / 100))
        if left <= 0:
            break                      # 这一回合它被砍死了，没机会还手
        damage += per_round_total
    if left > 0:
        return dict(base, ok=False, turns=turns, mon_damage=per_round,
                    atk_damage=atk_damage, lethal=True, reason="打不死",
                    notes=notes + ["打不死：回合数超过上限（它一直回血？）"])

    if traits.get("self_destruct") and hero_hp and damage < hero_hp - 1:
        damage = hero_hp - 1
        extra_notes.append("自爆：打完血只剩 1")
    # 打不打得过 = 这一场真实要的血 >= 你身上的血
    dead = bool(hero_hp) and damage >= hero_hp
    if dead:
        extra_notes.append("打不过：这一场要 %d 点血，你只有 %d"
                           % (damage, hero_hp))
    if notes and extra_notes:
        notes = notes + extra_notes
    return dict(base, ok=True, turns=turns, mon_damage=per_round,
                atk_damage=atk_damage, damage=damage,
                hero_hp_after=0 if dead else max(0, hero_hp - damage),
                lethal=dead,
                reason="打不过" if dead else "",
                degenerate=traits.get("degenerate") or (0, 0),
                notes=notes)


# ---- 一串东西：怪 + 宝石/血瓶，按顺序来 ----
_STAT_WORDS = (
    # 血瓶有几种写法：表里的"体力 +150"/"生命 +2000"，读图时的"回复300"，
    # 以及合并血瓶时的兜底"回血"（后面两种都得认成加血，否则血瓶白捡）
    ("hp", ("生命", "体力", "血量", "回血", "回复", "恢复", "加血")),
    ("atk", ("攻击",)),
    ("def", ("防御",)),
    ("mdef", ("魔防", "法术防御")),
)


def parse_item_effect(text: str) -> dict:
    """资源的一句话 → 属性加成：`"攻击力 +2"` → `{"atk": 2}`。

    支持一格里写好几项（"生命 +1000 · 攻击 +6"），也支持 `+`/`-`。
    """
    out = {}
    body = str(text or "")
    if not body:
        return out
    for key, words in _STAT_WORDS:
        for word in words:
            for match in re.finditer(
                    word + r"[力]?\s*([-+]?\s*\d+(?:\.\d+)?\s*[万kK亿]?)", body):
                amount = parse_amount(match.group(1).replace(" ", ""))
                if amount:
                    out[key] = out.get(key, 0) + amount
            if key in out:
                break
    return out


def step_count(step) -> int:
    """这一步重复几次（用户："点缩略图可以修改参数" —— 打 3 只、吃 2 个）。"""
    value = (step or {}).get("count")
    if value is None or value == "":
        return 1
    count = parse_amount(value)
    return max(1, min(999, count))


def run_plan(hero, steps) -> dict:
    """按顺序走一遍"这串东西"：每只怪掉多少血、吃到宝石/血后属性怎么变。

    steps: `[{"kind": "monster", "name": ..., "hp": ..., "atk": ..., "def": ...,
              "skills": [...]},
             {"kind": "item", "name": "红宝石", "effect": "攻击力 +2"}]`
    返回 `{"rows": [...], "total_damage": int, "hp_after": int, "dead_at": index,
            "unhandled": [...], "stats": {...}}`；
    每行的 `stats` 是"走过这一步之后"的属性（退化技能会扣攻防）。
    """
    stats = {"hp": max(0, parse_amount((hero or {}).get("hp"))),
             "atk": max(0, parse_amount((hero or {}).get("atk"))),
             "def": max(0, parse_amount((hero or {}).get("def"))),
             "mdef": max(0, parse_amount((hero or {}).get("mdef")))}
    rows = []
    total_damage = 0
    dead_at = -1
    unhandled = []
    for index, step in enumerate(steps or []):
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "monster")
        count = step_count(step)
        # 前面已经打不过了：后面的步骤照样列出来（标灰），但不再算
        if dead_at >= 0:
            rows.append({"kind": kind, "name": str(step.get("name") or ""),
                         "effect": str(step.get("effect") or ""),
                         "count": count,
                         "damage": 0, "turns": 0, "ok": False,
                         "reason": "前面就打不过了", "dead": True,
                         "hp_after": 0, "stats": dict(stats),
                         "gains": {}, "notes": [], "unhandled": []})
            continue
        if kind == "empty":
            # 界面上"勇者 → ?"还没选东西的一行：占着位置，不算任何东西
            rows.append({"kind": kind, "name": "", "effect": "",
                         "count": 1, "damage": 0, "turns": 0, "ok": False,
                         "reason": "", "dead": False, "hp_after": stats["hp"],
                         "stats": dict(stats), "gains": {}, "notes": [],
                         "unhandled": []})
            continue
        if kind == "item":
            gains = parse_item_effect(step.get("effect"))
            total_gains = {}
            for key, value in gains.items():
                stats[key] = max(0, stats.get(key, 0) + value * count)
                total_gains[key] = value * count
            rows.append({"kind": "item", "name": str(step.get("name") or ""),
                         "effect": str(step.get("effect") or ""),
                         "count": count,
                         "damage": 0, "turns": 0, "ok": True,
                         "hp_after": stats["hp"], "stats": dict(stats),
                         "gains": total_gains, "notes": [], "unhandled": []})
            continue
        result = fight(stats, step, step.get("skills"))
        lethal = bool(result.get("lethal"))
        if result["ok"]:
            one = int(result["damage"] or 0)
            total_damage += one * count
            before = stats["hp"]
            stats["hp"] = max(0, before - one * count)
            if before and stats["hp"] <= 0:
                lethal = True
        down_atk, down_def = result.get("degenerate") or (0, 0)
        if down_atk or down_def:
            stats["atk"] = max(0, stats["atk"] - down_atk * count)
            stats["def"] = max(0, stats["def"] - down_def * count)
        row = {"kind": "monster", "name": result["name"],
               "damage": (None if result["damage"] is None
                          else int(result["damage"]) * count),
               "turns": int(result["turns"] or 0) * count,
               "mon_damage": result.get("mon_damage"),
               "atk_damage": result.get("atk_damage"),
               "count": count,
               "ok": result["ok"], "reason": result.get("reason", ""),
               "lethal": lethal,
               "notes": result.get("notes") or [],
               "unhandled": result.get("unhandled") or [],
               "hp_after": stats["hp"], "stats": dict(stats)}
        rows.append(row)
        for item in row["unhandled"]:
            if item not in unhandled:
                unhandled.append(item)
        if result.get("lethal") and dead_at < 0:
            dead_at = index
    return {"rows": rows, "total_damage": total_damage,
            "hp_after": stats["hp"], "dead_at": dead_at,
            "unhandled": unhandled, "stats": dict(stats)}
