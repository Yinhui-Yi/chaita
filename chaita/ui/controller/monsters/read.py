"""给界面读的那几个列表和统计：怪物记录、技能汇总、模板、技能表、塔名。"""

import re

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...toolkit.library import _monster_skill_items
from ...toolkit.notes import _save_skill_notes

class ReadMixin:
    def _get_monsters(self):
        out = []
        for monster in self._monsters:
            item = dict(monster)
            # 界面按 skill_items 一行一个画技能（老数据在这里补齐）
            item["skill_items"] = _monster_skill_items(monster)
            out.append(item)
        return out

    def _map_monster_names(self):
        """地图记录里出现过的怪名（用户："技能只显示地图上添加的怪的技能"）。"""
        names = []
        seen = set()
        for entry in self._map_history:
            for mon in (entry.get("mons") or []):
                name = (mon or {}).get("name") or ""
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
        return names

    def _get_skill_stats(self):
        """把技能摊平：一行一个技能，只统计**地图上加过的怪**。

        用户明确要求："技能只显示地图上添加的怪的技能" —— 手册里读了一堆但地图上
        没加过的怪，技能不该堆在这里。数量按"地图上出现的怪种类"算（不用只数：
        模型在地图上数不准，给出来的数字是假的）。

        每一项还带两样给人看的东西（用户："点了之后不要展示无效信息，要展示
        具体效果，而且能改数值"）：
          effect —— 游戏手册上对这个技能的原话（`skillinfo.effect_for`）
          mons   —— 带这个技能的怪，一只一行，每行带**这只怪自己的**数值
                    （同名技能在第 1 层和第 50 层不一样，所以值挂在怪身上）
        """
        on_map = set(self._map_monster_names())
        counts = {}
        order = []
        values = {}
        rows = {}
        for index, monster in enumerate(self._monsters):
            name = monster.get("name") or ""
            if name not in on_map:
                continue                      # 地图上没加过这只怪，它的技能不算
            seen = set()
            for entry in _monster_skill_items(monster):
                token = entry["name"]
                if not token or token in seen:
                    continue      # 同一只怪重复出现的技能只算一次
                seen.add(token)
                if token not in counts:
                    counts[token] = 0
                    order.append(token)
                    values[token] = []
                    rows[token] = []
                counts[token] += 1
                value = (entry.get("value") or "").strip()
                if value and value not in values[token]:
                    values[token].append(value)
                rows[token].append({"index": index, "name": name,
                                    "count": monster.get("count"),
                                    "value": value})
        # values：各只怪给这个技能记的数值（同名技能不同层数值可能不一样）
        return [{"skill": token, "count": counts[token],
                 "values": values[token],
                 "effect": self._effect_of(token)[0],
                 "mons": rows[token]} for token in order]

    # ---- 技能介绍：用户写的 > 内置的手册原话 > 某只怪上手写的（老数据） ----
    def _effect_of(self, token) -> tuple:
        """这个技能现在该显示的介绍：`(文字, 来源)`，来源是 note / builtin / monster / ""。

        - note：用户在技能介绍卡里写（不在内置表里的技能）或改写（不同的魔塔数值不同）的，
          优先于内置的；
        - builtin：assets/skill_effects.json 里的手册原话（只读的底）；
        - monster：以前在怪物编辑卡里给某只怪写的自定义介绍（老数据，读得出来不丢）。
        """
        from ....game import skillinfo

        name = (token or "").strip()
        if not name:
            return "", ""
        note = (getattr(self, "_skill_notes", {}) or {}).get(name, "")
        if note:
            return note, "note"
        built = skillinfo.effect_for(name)
        if built:
            return built, "builtin"
        for monster in self._monsters:
            for entry in _monster_skill_items(monster):
                text = str(entry.get("effect") or "").strip()
                if entry["name"] == name and text:
                    return text, "monster"
        return "", ""

    @Slot(str, result="QVariantMap")
    def skillIntro(self, name: str) -> dict:
        """技能介绍卡要的东西：`{text, source, hasBuiltin, edited}`。

        hasBuiltin：内置表里有这个技能的手册原话；edited：用户改写过它
        （改写过才有「恢复原话」）。
        """
        from ....game import skillinfo

        token = (name or "").strip()
        text, source = self._effect_of(token)
        has_builtin = bool(skillinfo.effect_for(token))
        return {"text": text, "source": source, "hasBuiltin": has_builtin,
                "edited": source == "note" and has_builtin}

    @Slot(str, str)
    def setSkillNote(self, name: str, text: str) -> None:
        """记下用户写/改写的技能介绍。

        写成空、或者和内置原话一字不差，都等于「没有改写」：删掉那一条（也就是恢复原话）。
        """
        from ....game import skillinfo

        token = (name or "").strip()
        if not token:
            return
        clean = (text or "").strip()
        notes = dict(getattr(self, "_skill_notes", {}) or {})
        if clean == "" or clean == skillinfo.effect_for(token):
            notes.pop(token, None)
        else:
            notes[token] = clean
        if notes == getattr(self, "_skill_notes", {}):
            return
        self._skill_notes = notes
        _save_skill_notes(notes)
        self.skillStatsChanged.emit()

    def _get_monster_templates(self):
        return list(self._monster_templates)

    def _get_skill_catalog(self):
        """下拉里能选的技能：库里的目录 + 手册/模板里实际出现过的（手打的老名字也不丢）。"""
        out = list(self._skill_catalog)
        seen = set(out)
        extra = []
        for row in list(self._monsters) + list(self._monster_templates):
            tokens = [entry["name"] for entry in _monster_skill_items(row)]
            if not tokens:
                tokens = [t for t in re.split(r"[\s,，、/;；]+",
                                              (row.get("skills") or "").strip()) if t]
            for token in tokens:
                if token and token not in seen:
                    seen.add(token)
                    extra.append(token)
        extra.sort()
        return out + extra

    def _get_tower_label(self):
        return self._tower_label

    @Slot(str, result=str)
    def skillEffect(self, name: str) -> str:
        """这个技能现在的介绍（用户写的优先，没有就是游戏手册上的原话）。"""
        return self._effect_of(name)[0]

    @Slot(str, result="QVariantList")
    def skillParams(self, name: str) -> list:
        """这个技能要填哪几个数：`[{field, label, unit, type}]`。

        field 就是引擎里的 `enemy.<字段>`（破甲 defValue、吸血 value+add……），
        以后算伤害按 code + 这几个数走，不再从文本里抠数字。
        """
        from ....game import skillinfo
        return skillinfo.params_for(name)

    @Slot(str, result=str)
    def skillCode(self, name: str) -> str:
        """技能名 → 引擎 code（将来算伤害的键）。查不到返回空串。"""
        from ....game import skillinfo
        return skillinfo.code_for(name)

    @Slot(str, result=str)
    def libraryUrl(self, entry_id: str) -> str:
        from .... import library
        return library.url_of(entry_id)

    # 「＋加资源」的下拉：owner 指定过的资源（assets/items/map.json）
