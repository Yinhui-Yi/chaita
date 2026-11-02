"""伤害计算器：给界面提供"人物当前状态 + 可选怪/物品 + 算一串东西"。

用户："做一个伤害计算的功能：1.可以根据人物的当前状态计算掉血 2.给一连串东西
（怪、宝石、血），要给出打每个怪的掉血及最终掉血 3.考虑技能、考虑多技能兼容
4.思考入口该加在哪里才合理"。

界面只负责摆列表，真正的公式在 `chaita/game/battle.py`（纯函数、有单元测试）。
这里只做三件事：把状态行读到的数值给出去、把手册里的怪/素材库里的物品摊平、
把界面传回来的 JSON 交给 `battle.run_plan`。
"""

import json

from PySide6.QtCore import Slot

from ...ui.toolkit.library import _monster_skill_items

# 手册里查不到这只怪时，界面上写的原因（"加属性收益"里那一行灰字）
_NO_HANDBOOK_VALUES = "手册里没有它的数值"


class BattleMixin:
    # ---- 人物当前状态（状态行读到的那些数） ----
    @Slot(result="QVariantMap")
    def battleHero(self) -> dict:
        """人物当前的 血/攻/防/魔防（读不到就是 0，界面上可以手改）。"""
        from ...game import battle
        status = self._last_status if isinstance(self._last_status, dict) else {}
        hero = {}
        for key in ("hp", "atk", "def", "mdef"):
            hero[key] = battle.parse_amount(status.get(key))
        hero["tower"] = str(self._tower_label or "")
        return hero

    # ---- 能加进这串东西的怪（怪物手册里的） ----
    @Slot(result="QVariantList")
    def battleMonsters(self) -> list:
        """`[{name, hp, atk, def, skills:[{name,code,params}], skillsText, icon}]`。

        数值原样给（可能是 "21000万"，公式那边会自己解析）；技能带 code 和参数，
        因为"破甲 50%"和"破甲 0%"算出来完全不一样。
        """
        from ...game import battle, skillinfo
        out = []
        for monster in self._monsters or []:
            if not isinstance(monster, dict):
                continue
            name = str(monster.get("name") or "").strip()
            if not name:
                continue
            items = _monster_skill_items(monster)
            skills = []
            for item in items:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                skill_name = str(item.get("name") or "")
                # schema 给界面画参数格子（破甲是"防御百分比 %"这种）
                skills.append({"name": skill_name,
                               "code": str(item.get("code") or ""),
                               "params": dict(item.get("params") or {}),
                               "schema": skillinfo.params_for(skill_name)})
            out.append({
                "name": name,
                "hp": battle.parse_amount(monster.get("hp")),
                "atk": battle.parse_amount(monster.get("atk")),
                "def": battle.parse_amount(monster.get("def")),
                "skills": skills,
                "skillsText": " · ".join(skill["name"] for skill in skills),
                "icon": str(monster.get("icon") or ""),
            })
        return out

    # ---- 能加进这串东西的物品（宝石/血瓶/武器/防具，效果从素材表里来） ----
    @Slot(result="QVariantList")
    def battleItems(self) -> list:
        """`[{name, icon, effect}]`：只留**算得出加成**的东西。

        用户："点问号后添加的界面里面没用的东西太多了，应该只有两个标签页分别是
        怪物和资源（包含 4 色宝石）"。

        素材表里 76 条资源有一大半是书/证明/锄头这种和掉血无关的；能不能算出
        「攻击/防御/生命/魔防 +N」用 `battle.parse_item_effect()` 判 —— 和真正
        计算用的是同一个解析器，不会出现"列表里有、加进去却没效果"。
        """
        from ...game import iteminfo
        from ...game import battle
        out = []
        try:
            choices = iteminfo.choices()
        except Exception:
            choices = []
        for entry in choices:
            stem = str(entry.get("icon") or "")
            effect = str(entry.get("effect") or "")
            kind = iteminfo.kind_rank(str(entry.get("name") or ""), stem)
            # 宝石无条件留（绿宝石加敏捷、公式里没这一项但玩家要选它）；
            # 武器/防具也留（默认 +0，数值由用户在那一行里改，进路线）。
            # 其余只有"算得出加成"才摆出来。
            if not (iteminfo.is_gem(stem) or kind in (1, 2)):
                if not effect or not battle.parse_item_effect(effect):
                    continue
            out.append({"name": str(entry.get("name") or stem),
                        "icon": stem, "effect": effect})
        return out

    # ---- 算 ----
    @Slot(str, result="QVariantMap")
    def computeBattle(self, payload: str) -> dict:
        """payload = `{"hero": {...}, "steps": [...]}` → 每一步的掉血 + 合计。"""
        from ...game import battle
        from ... import trace
        try:
            data = json.loads(payload or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        hero = data.get("hero") if isinstance(data.get("hero"), dict) else {}
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        result = battle.run_plan(hero, steps)
        trace.note("battle.compute", steps=len(steps), hero=hero,
                   total=result.get("total_damage"),
                   dead_at=result.get("dead_at"))
        return result

    @Slot(str, result="QVariantMap")
    def propertyGain(self, payload: str) -> dict:
        """再加 X 点攻/防/魔防，**剩下的怪**少掉多少血（按层分组给界面用）。

        用户 2026-11-01："每增加 x 点攻击防御魔防，剩下的怪会减少多少伤害：对于每一只
        怪 / 对于每一种（一只 × 数量）/ 对于剩下所有怪，需要可以配上界，超过上界的按
        上界计算"，"三项各一个输入框 可以同时修改"、"上界封所有"；随后又说
        "这是新功能！！！不要和之前的混在一起！！！" —— 它是自己那扇窗
        （`views/property_gain/GainWindow.qml`），和伤害计算没有关系。

        payload = `{"gain": {"atk": x, "def": x, "mdef": x}, "cap": n}`

        返回（界面只照着画，不再自己算）：
            floors   [{floor, species:[{name, count, one, all}],
                       unknown:[{name, count, reason}], saved, count}]
                     一层一组：`one` = 一只少掉、`all` = 这一种一共少掉；
                     `unknown` 是手册里没数值 / 算不了的，写清原因、不计入合计
            total_saved / capped_saved / capped / cap   合计（上界只封合计）
            count_species / count_monsters              剩下几种 / 几只
            hero                                        这次算的是哪一份属性
        """
        from ...game import battle
        from ... import trace
        try:
            data = json.loads(payload or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        gain = data.get("gain") if isinstance(data.get("gain"), dict) else {}
        hero = self.battleHero()
        floors = []
        total_saved = 0
        species_count = 0
        monsters_count = 0
        for group in self._remaining_by_floor():
            known = [row["monster"] for row in group["rows"]
                     if row.get("monster")]
            # 每层各算各的（上界只封合计，所以这里一律不封）：
            # `per_monster` 和 `uncomputable` 就都自然带着层，不用回头认名字。
            got = battle.damage_gain(hero, known, gain=gain, cap=0)
            count_of = {row["name"]: row["count"] for row in group["rows"]}
            rows = [{"name": one["name"], "count": one["count"],
                     "one": one["saved"], "all": one["saved"] * one["count"]}
                    for one in got.get("per_monster") or []]
            unknown = [{"name": row["name"], "count": row["count"],
                        "reason": row["reason"]}
                       for row in group["rows"] if not row.get("monster")]
            unknown += [{"name": one["name"],
                         "count": count_of.get(one["name"], 1),
                         "reason": one["reason"]}
                        for one in got.get("uncomputable") or []]
            if not rows and not unknown:
                continue
            total_saved += int(got.get("total_saved") or 0)
            species_count += len(rows)
            monsters_count += sum(one["count"] for one in rows)
            floors.append({"floor": group["floor"], "species": rows,
                           "unknown": unknown,
                           "saved": int(got.get("total_saved") or 0),
                           "count": sum(one["count"] for one in rows)})
        result = {"floors": floors, "hero": hero, "gain": dict(gain),
                  "total_saved": total_saved,
                  "count_species": species_count,
                  "count_monsters": monsters_count}
        result.update(battle.apply_cap(total_saved, data.get("cap") or 0))
        trace.note("gain.calc", gain=gain, cap=data.get("cap"),
                   total=total_saved, capped=result.get("capped_saved"),
                   floors=len(floors), species=species_count)
        return result

    def _remaining_by_floor(self) -> list:
        """各层**还没打**的怪，按层分好：`[{floor, rows}]`。

        `rows` 一格一种：`{name, count, monster, reason}`。
        - 清单里 `done` 为真的跳过（打过了就不再算进"剩下"）；
        - 同一层同名合并数量；数量没填就当 1 只；
        - 手册里查不到的 `monster` 是 None、`reason` 写清为什么 —— 不硬算
          （编出来的数字比不显示更坏）。
        """
        from ...game import battle
        known = {}
        for monster in self._monsters or []:
            if isinstance(monster, dict):
                known[str(monster.get("name") or "").strip()] = monster
        floors = []
        for entry in self._map_history or []:
            if not isinstance(entry, dict):
                continue
            counts = {}
            order = []
            for row in entry.get("mons") or []:
                if not isinstance(row, dict) or row.get("done"):
                    continue
                name = str(row.get("name") or "").strip()
                if not name:
                    continue
                count = row.get("count")
                count = 1 if count in (None, "") else max(
                    0, battle.parse_amount(count))
                if name not in counts:
                    counts[name] = 0
                    order.append(name)
                counts[name] += count
            if not order:
                continue
            rows = []
            for name in order:
                handbook = known.get(name)
                if not handbook:
                    rows.append({"name": name, "count": counts[name],
                                 "monster": None,
                                 "reason": _NO_HANDBOOK_VALUES})
                    continue
                rows.append({
                    "name": name, "count": counts[name], "reason": "",
                    "monster": {"name": name,
                                "hp": battle.parse_amount(handbook.get("hp")),
                                "atk": battle.parse_amount(handbook.get("atk")),
                                "def": battle.parse_amount(handbook.get("def")),
                                "skills": _monster_skill_items(handbook),
                                "count": counts[name]}})
            floors.append({"floor": str(entry.get("floor") or ""),
                           "rows": rows})
        return floors
