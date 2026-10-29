"""增删改：按模板加一只、保存（名字/血攻防/技能参数/图标）、排序、删、改技能数值。"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...toolkit.library import (_fill_skill_codes, _import_icon,
                                _monster_skill_items, _parse_skill_payload,
                                _skill_items_from_text, _skill_names)

class EditMixin:
    @Slot(str, str, str, str, str, str, str)
    def addMonsterTpl(self, name, hp, atk, def_, exp, skills, icon) -> None:
        from .... import trace
        text = (skills or "").strip()
        item = {
            "name": (name or "").strip() or "新怪物",
            "hp": (hp or "").strip(), "atk": (atk or "").strip(),
            "def": (def_ or "").strip(), "exp": (exp or "").strip(),
            # 金币是手册上没有、只有用户自己知道的东西（打这只怪掉多少钱）
            "gold": "",
            "skills": text,
            "skill_items": _fill_skill_codes(_skill_items_from_text(text)),
            "count": None, "icon": (icon or "").strip(), "icon_id": "",
        }
        self._monsters = list(self._monsters) + [item]
        self.monstersChanged.emit()
        trace.note("manual.add_monster_tpl", name=item["name"],
                   has_icon=bool(item["icon"]), total=len(self._monsters))

    @Slot(int, str, str, str, str, str, str, str, str, str)
    @Slot(int, str, str, str, str, str, str, str, str)
    def saveMonsterFull(self, index: int, name: str, hp: str, atk: str,
                        def_: str, exp: str, skills: str, icon_id: str,
                        icon_file: str, gold=None) -> None:
        """保存一只怪；icon_file 是用户上传的本地图片（file:// 或路径）。

        有上传图就复制进 assets/uploads/ 再存；否则沿用 saveMonster 的逻辑
        （icon_id 是素材库图；都不给就保留原来的图，别把模板带的图抹掉）。

        gold 传 None 表示调用方不知道有这一栏（老代码/老测试），那就别动原来的值；
        传 "" 是用户把金币栏清空了，要真的清掉。
        """
        from .... import library, trace
        monsters = list(self._monsters)
        if not (0 <= index < len(monsters)):
            return
        clean = (name or "").strip()
        if not clean:
            monsters.pop(index)
        else:
            item = dict(monsters[index])
            skill_items = _fill_skill_codes(_parse_skill_payload(skills))
            item.update({"name": clean, "hp": (hp or "").strip(),
                         "atk": (atk or "").strip(),
                         "def": (def_ or "").strip(),
                         "exp": (exp or "").strip(),
                         # skills 只留名字（老代码 / 技能区统计都还认它）；
                         # 数值挂在 skill_items 上：**同名技能不同层数值可以不一样**
                         "skills": _skill_names(skill_items),
                         "skill_items": skill_items})
            if gold is not None:
                item["gold"] = str(gold).strip()
            picked_url = _import_icon(icon_file, "monster_upload")
            if picked_url:
                item["icon"] = picked_url
                item["icon_id"] = ""
            elif icon_id:
                url = library.url_of(icon_id)
                if url:
                    item["icon"] = url
                    item["icon_id"] = icon_id
            monsters[index] = item
        # 不排序：改个名字就把这只怪挪到别处，用户会以为"顺序乱了"
        self._monsters = monsters
        self.monstersChanged.emit()
        trace.note("manual.save_monster", index=index, name=clean,
                   icon=icon_id, uploaded=bool(icon_file), gold=gold)

    @Slot(int, str, str, str, str, str, str, str)
    def saveMonster(self, index: int, name: str, hp: str, atk: str,
                    def_: str, exp: str, skills: str, icon_id: str) -> None:
        """保存一只怪；名字为空就删掉这条。"""
        from .... import library, trace
        monsters = list(self._monsters)
        if not (0 <= index < len(monsters)):
            return
        clean = (name or "").strip()
        if not clean:
            monsters.pop(index)
        else:
            item = dict(monsters[index])
            item.update({"name": clean, "hp": (hp or "").strip(),
                         "atk": (atk or "").strip(),
                         "def": (def_ or "").strip(),
                         "exp": (exp or "").strip(),
                         "skills": (skills or "").strip()})
            if icon_id:
                url = library.url_of(icon_id)
                if url:
                    item["icon"] = url
                    item["icon_id"] = icon_id
            monsters[index] = item
        self._monsters = monsters
        self.monstersChanged.emit()
        trace.note("manual.save_monster", index=index, name=clean,
                   icon=icon_id)

    @Slot(int, int)
    def moveMonster(self, from_index: int, to_index: int) -> None:
        """拖拽调整怪物顺序（用户："为什么我不可以通过拖拽调整怪物显示顺序"）。

        顺序是用户自己的（打法习惯：常查的怪放前面），所以存的就是列表顺序本身，
        不排序、不按名字、读手册也不重排。越界/原地不动就当没发生。
        """
        from .... import trace
        monsters = list(self._monsters)
        total = len(monsters)
        if not (0 <= from_index < total) or not (0 <= to_index < total):
            return
        if from_index == to_index:
            return
        item = monsters.pop(from_index)
        monsters.insert(to_index, item)
        self._monsters = monsters
        self.monstersChanged.emit()
        trace.note("manual.move_monster", name=item.get("name"),
                   start=from_index, end=to_index)

    @Slot(int)
    def removeMonster(self, index: int) -> None:
        from .... import trace
        monsters = list(self._monsters)
        if 0 <= index < len(monsters):
            monsters.pop(index)
        self._monsters = monsters
        self.monstersChanged.emit()
        trace.note("manual.remove_monster", index=index)

    @Slot(str)
    def removeMonsterByName(self, name: str) -> None:
        """从名单里彻底删掉这只：手册记录 + 各层地图里的记录。

        列表里那一行是"整座塔"的汇总。只删手册记录的话，地图上用到它的层还会
        把它顶出来 —— 用户点了删除却看着行没消失，等于按钮坏了。所以两处一起删。
        """
        from .... import trace
        target = (name or "").strip()
        if not target:
            return
        monsters = [m for m in self._monsters
                    if (m.get("name") or "").strip() != target]
        records = len(self._monsters) - len(monsters)
        self._monsters = monsters
        floors = []
        touched = 0
        for entry in self._map_history:
            if not isinstance(entry, dict):
                floors.append(entry)
                continue
            rows = list(entry.get("mons") or [])
            kept = [row for row in rows
                    if (row.get("name") or "").strip() != target]
            if len(kept) != len(rows):
                entry = dict(entry)
                entry["mons"] = kept
                touched += 1
            floors.append(entry)
        if touched:
            self._map_history = floors
            self.mapHistoryChanged.emit()
        self.monstersChanged.emit()
        trace.note("manual.remove_monster_name", name=target,
                   records=records, floors=touched)

    @Slot(int, str, str)
    def setMonsterSkillValue(self, index: int, skill: str, value: str) -> None:
        """改某只怪某个技能的数值（在技能区点开技能后直接改）。

        为什么值挂在怪身上：同名技能在第 1 层和第 50 层数值不一样，用户明确说过。
        所以这里只动 `this monster 的这个技能`，不碰技能目录、不碰别的怪。
        """
        from .... import trace
        monsters = list(self._monsters)
        if not (0 <= index < len(monsters)):
            return
        token = (skill or "").strip()
        if not token:
            return
        monster = dict(monsters[index])
        items = [dict(row) for row in _monster_skill_items(monster)]
        found = False
        for row in items:
            if str(row.get("name") or "").strip() == token:
                row["value"] = (value or "").strip()
                found = True
        if not found:
            # 老数据里这只怪只有 skills 串：补一条出来，别把用户填的值丢掉
            items.append({"name": token, "value": (value or "").strip()})
        monster["skill_items"] = items
        monster["skills"] = _skill_names(items)
        monsters[index] = monster
        self._monsters = monsters
        self.monstersChanged.emit()
        trace.note("manual.skill_value", index=index, skill=token,
                   value=(value or "").strip(), name=monster.get("name"))
