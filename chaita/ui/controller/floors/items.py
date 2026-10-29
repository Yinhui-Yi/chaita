"""这一层的资源行：排序、加一条、改名字/图标/效果/数量、删、勾。"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot


class ItemsMixin:
    @Slot(str, result="QVariantList")
    def sortedSheetItems(self, floor_text) -> list:
        """这一层的资源，**按魔塔里的习惯顺序**排好给界面（用户："资源怎么不按习惯排序"）。

        宝石（红蓝绿黄）→ 武器 → 防具 → 血瓶 → 钥匙 → 其他，同类里按颜色/数值排。
        每行带一个 `_src`（它在真实列表里的下标）：改名字/数量/删行都按 `_src` 走，
        不然按显示顺序存会存错行。

        图标和效果跟主界面同一条规则（`_fill_item_display`）：刷新读进来的行
        只存了名字和数量，图得在这儿补（用户："读进来的资源还是没有图标"）。
        """
        from ....game import iteminfo
        position = self._find_floor(floor_text)
        if position < 0:
            return []
        entry = self._map_history[position] or {}
        rows = []
        for index, item in enumerate(entry.get("items") or []):
            if not isinstance(item, dict):
                continue
            row = self._fill_item_display(item)
            row["_src"] = index
            rows.append(row)
        return iteminfo.sort_items(rows)

    @Slot(str, str, str, str, str, result=int)
    def addItemFull(self, floor_text, name, effect, count, icon) -> int:
        """一次性加一条资源（名字/效果/数量/图标），返回它的位置。

        和 addFloorMonsterFull 同理：草稿保存只调这一个，避免"改完模型、组件没了、
        后续语句不执行"。
        """
        from .... import trace
        from ....game import iteminfo
        position = self._find_floor(floor_text)
        if position < 0:
            return -1
        clean = (name or "").strip()
        if not clean:
            return -1
        picked = (icon or "").strip()
        if picked and iteminfo.icon_exists(picked):
            try:
                iteminfo.save_icon_map(clean, picked)
            except Exception as exc:
                trace.note("manual.icon_save_failed", error=repr(exc)[:160])
                picked = ""
        else:
            picked = ""
        digits = "".join(ch for ch in (count or "") if ch.isdigit())
        updated = dict(self._map_history[position])
        items = list(updated.get("items") or [])
        # 效果：调用方给了就用给的（手填 / AI 读到的），没给才回落到道具表默认值
        auto_effect = iteminfo.effect_for(picked, clean)
        items.append({"name": clean,
                      "effect": (effect or "").strip() or auto_effect,
                      "count": int(digits) if digits else None,
                      "icon": picked or iteminfo.icon_for(clean)})
        # 用户："资源怎么不按习惯排序" —— 钥匙 → 血药 → 宝石 → 武器 → 防具 → 其他
        items = iteminfo.sort_items(items)
        updated["items"] = items
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
        trace.note("manual.add_item", floor=floor_text, name=clean,
                   count=count, total=len(items))
        added = next((i for i, item in enumerate(items)
                      if str(item.get("name") or "") == clean
                      and str(item.get("icon") or "") ==
                      str((picked or iteminfo.icon_for(clean)))), -1)
        return added if added >= 0 else len(items) - 1

    @Slot(str, int, str, str, str)
    def setItemKind(self, floor_text, index, name, icon, effect) -> None:
        """把这一条资源换成另一种（点资源图标换种类：钥匙/剑/盾/血瓶…）。

        用户："地图下的资源只有数值和数量能改" —— 名字、图标、默认效果一起换掉。
        """
        from .... import trace
        from ....game import iteminfo
        position = self._find_floor(floor_text)
        if position < 0:
            return
        updated = dict(self._map_history[position])
        items = list(updated.get("items") or [])
        if not (0 <= index < len(items)):
            return
        clean = (name or "").strip()
        if not clean:
            return
        stem = (icon or "").strip() or iteminfo.icon_for(clean)
        auto = iteminfo.effect_for(stem, clean)
        row = dict(items[index])
        row["name"] = clean
        row["icon"] = stem
        row["effect"] = auto or (effect or "")
        row.pop("effect_manual", None)
        items[index] = row
        items = iteminfo.sort_items(items)
        updated["items"] = items
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
        trace.note("manual.item_kind", floor=floor_text, name=clean, icon=stem)

    @Slot(str, int, str, str)
    def saveItemField(self, floor_text, index, field, text) -> None:
        """只改一条资源的某一个字段（数量 / 名字 / 效果），改完立刻落库。

        界面上只有**数量**是可编辑的：名字和效果跟着资源种类走（用户：
        "为什么可以交叉使用图片素材，具体效果为什么不写死"）。名字/效果这两个
        分支留着给测试和以后"素材库纠错"用。

        每存一次发一个"已存"回执：用户改完要能看出到底存没存
        （用户："修改的状态和修改完成的状态没有差别"）。
        """
        from ....game import iteminfo
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return
        updated = dict(self._map_history[position])
        items = [dict(item) for item in (updated.get("items") or [])]
        if not (0 <= index < len(items)):
            return
        value = (text or "").strip()
        if field == "name":
            if value == "":
                items.pop(index)
                updated["items"] = items
                self._map_history[position] = updated
                self.mapHistoryChanged.emit()
                trace.note("manual.remove_item", floor=floor_text, index=index,
                           why="name_cleared")
                return
            items[index]["name"] = value
            # 名字改了：图标按新名字重新找（"红血瓶"改成"黄钥匙"就要换图，
            # 用户："地图下的资源只有数值和数量能改"）；效果没手改过也跟着换
            fresh = iteminfo.icon_for(value)
            if fresh:
                items[index]["icon"] = fresh
            if not items[index].get("effect_manual"):
                auto = iteminfo.effect_for(items[index].get("icon") or "", value)
                if auto:
                    items[index]["effect"] = auto
        elif field == "effect":
            items[index]["effect"] = value
            # 手改过就打标记：显示层不再拿道具表覆盖；清空则退回跟表走
            if value != "":
                items[index]["effect_manual"] = True
            else:
                items[index].pop("effect_manual", None)
        elif field == "count":
            digits = "".join(ch for ch in value if ch.isdigit())
            items[index]["count"] = int(digits) if digits else None
        else:
            return
        # 改名字会换种类，顺序按习惯重排；只改数量/效果时顺序不该跳
        if field == "name":
            items = iteminfo.sort_items(items)
        updated["items"] = items
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
        self._mark_saved("item", floor_text, index)
        trace.note("manual.item_field", floor=floor_text, index=index,
                   field=field, value=value)

    @Slot(str, result=str)
    def itemEffectLabel(self, text) -> str:
        """效果里的"属性"那半截（写死，不可改）：`"攻击力 +2"` → `"攻击力"`。

        用户："宝石加的属性要写死，加的数值要能改"。
        """
        from ....game import iteminfo
        return iteminfo.split_effect(text)[0]

    @Slot(str, result=str)
    def itemEffectValue(self, text) -> str:
        """效果里的"数值"那半截（可改）；没有数值（"可以打开一扇黄门"）给空串。"""
        from ....game import iteminfo
        return iteminfo.split_effect(text)[1]

    @Slot(str, str, result=str)
    def itemEffectJoin(self, label, value) -> str:
        """把"属性 + 数值"拼回去（`("攻击力", "99")` → `"攻击力 +99"`）。

        拼的规则只在 `iteminfo.join_effect` 里有一份：伤害计算的资源步骤也用它，
        不然同一件事在两处各写一遍，迟早对不上。
        """
        from ....game import iteminfo
        return iteminfo.join_effect(label, value)

    @Slot(str, result="QVariantMap")
    def itemEffectParts(self, text) -> dict:
        """效果拆成三截：属性 / 符号 / 数字（`"攻击力 +2"` → 攻击力 / + / 2）。

        用户："我说的是「攻击力」三个字"、"怎么加号不是固定的？" ——
        属性和加号都该是写死的字，只有数字进输入框。所以界面上要这三截，
        拆法还是 `iteminfo.split_effect` 那一份（不在 QML 里再切一遍字符串）。
        """
        from ....game import iteminfo
        label, amount = iteminfo.split_effect(text)
        sign = amount[:1] if amount[:1] in ("+", "-") else ""
        return {"label": label, "sign": sign,
                "digits": amount[len(sign):] if sign else amount}

    @Slot(str, int, str)
    def saveItemEffectValue(self, floor_text, index, value) -> None:
        """只改效果里的**数值**：属性那半截保持道具表写的。

        用户："宝石加的属性要写死，加的数值要能改"（不同塔的同一颗宝石可能 +2 也可能 +5）。
        """
        from ....game import iteminfo
        position = self._find_floor(floor_text)
        if position < 0:
            return
        items = list(self._map_history[position].get("items") or [])
        if not (0 <= index < len(items)):
            return
        row = items[index] if isinstance(items[index], dict) else {}
        label, _old = iteminfo.split_effect(row.get("effect") or "")
        if not label:
            # 还没有效果（新加的一行）：属性取道具表，数值用用户输的
            label = iteminfo.split_effect(iteminfo.effect_for(
                str(row.get("icon") or ""), str(row.get("name") or "")))[0]
        self.saveItemField(floor_text, index, "effect",
                           iteminfo.join_effect(label, value))

    @Slot(str, result="QVariantList")
    def itemEffectPartList(self, text) -> list:
        """效果拆成若干段给界面画：`[{label, sign, digits}]`，一段一个数字框。

        用户 2026-10-28："黄宝石每个值都要能改"——多段效果（`攻击力 +1 · 防御力
        +1 · 魔防 +2`）不能当成一句话，每段都要有自己的加减框。
        """
        from ....game import iteminfo
        return [{"label": label, "sign": sign, "digits": digits}
                for label, sign, digits in iteminfo.split_effect_parts(text)]

    @Slot(str, int, str, result=str)
    def itemEffectWithPart(self, text, part_index, value) -> str:
        """把第 `part_index` 段的数值换掉，其余段原样——拼法只有 `iteminfo` 一处。"""
        from ....game import iteminfo
        return iteminfo.effect_with_part(text, part_index, value)

    @Slot(str, int, int, str)
    def saveItemEffectPartValue(self, floor_text, index, part_index, value) -> None:
        """改多段效果里第 `part_index` 段的数值（每段一个框，改哪段只动哪段）。"""
        from ....game import iteminfo
        position = self._find_floor(floor_text)
        if position < 0:
            return
        items = list(self._map_history[position].get("items") or [])
        if not (0 <= index < len(items)):
            return
        row = items[index] if isinstance(items[index], dict) else {}
        effect = iteminfo.effect_with_part(row.get("effect") or "",
                                           part_index, value)
        self.saveItemField(floor_text, index, "effect", effect)

    @Slot(str, int)
    def removeItem(self, floor_text, index) -> None:
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return
        updated = dict(self._map_history[position])
        items = list(updated.get("items") or [])
        if 0 <= index < len(items):
            items.pop(index)
        updated["items"] = items
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
        trace.note("manual.remove_item", floor=floor_text, index=index)

    @Slot(str, int)
    def toggleFloorItemDone(self, floor_text, index) -> None:
        """这个资源拿过了 / 撤销。"""
        self._toggle_done(floor_text, index, "items")

    # ---- 打过了 / 拿过了：一行行勾掉，一眼看这一层还剩什么 ----
    # 只动这一个布尔值：不改名字、不改数量、不重新排序，勾完手指还在原位。

    def _toggle_done(self, floor_text, index, key):
        from .... import trace
        position = self._find_floor(floor_text)
        if position < 0:
            return
        updated = dict(self._map_history[position])
        rows = [dict(row) for row in (updated.get(key) or [])]
        if not (0 <= index < len(rows)):
            return
        rows[index]["done"] = not bool(rows[index].get("done"))
        updated[key] = rows
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
        trace.note("manual.toggle_done", floor=floor_text, kind=key,
                   index=index, done=rows[index]["done"],
                   name=rows[index].get("name"))
