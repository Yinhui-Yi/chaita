"""图标这一摊：素材库候选/分组、按名字找图、最大边长（缩放上限）、换图。"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

class IconsMixin:
    # ---- 素材库：给怪物编辑器列图、按 id 取图 ----

    @Slot(result="QVariantList")
    def monsterIconChoices(self) -> list:
        """素材库里"怪物"的候选：`{id, name, aliases, url}`（顺序就是显示顺序）。

        用 `library.pictures()` 而不是 `items()`：素材是按动画帧导进来的，
        同一只怪有 `120_0` / `120_1` 两帧；不去重的话选图界面里每只怪都重复
        （用户："素材库内有大量重复"）。

        名字一起来（用户："素材库改成图片加名称且需要支持搜索"）：塔里的怪物图
        名字就是怪物名（红色史莱姆 / 黑衣魔王…），经典素材没有名字就用编号。
        """
        out = []
        for group in self.monsterIconGroups():
            out.extend(group.get("items") or [])
        return out

    @Slot(result="QVariantList")
    def monsterIconGroups(self) -> list:
        """素材库按"类"分好的组：`[{kind, items}]`。

        用户："我想了一下还是一个种族放一行" —— 界面按组排版，每一类都从新的一行
        开始（`iconCells()` 里用空格子把上一类补齐到整行）。
        """
        from .... import library
        groups = []
        for entry in library.pictures("monster")[:400]:
            entry_id = str(entry.get("id") or "")
            if not entry_id:
                continue
            kind = str(entry.get("kind") or library.UNKNOWN_KIND)
            if not groups or groups[-1]["kind"] != kind:
                groups.append({"kind": kind, "items": []})
            groups[-1]["items"].append(
                {"id": entry_id,
                 "name": library.display_name(entry),
                 # 两座塔各存一份的图只留一张，另一条的名字挂在这
                 "aliases": list(entry.get("aliases") or []),
                 "url": library.url_of(entry_id)})
        return groups

    @Slot(str, result=str)
    def libraryIconByName(self, name: str) -> str:
        """素材库里按名字找一张图（「这一层」的怪物行没有手册记录时兜底）。

        用户："怪物和资源的缩略图怎么没有了" —— 以前地图行只认这次读手册抠下来的
        临时图，没读过手册的怪就只剩一个首字。素材库里有名字（显示名 / 两座塔里的
        原名 / 并掉的别名），能对上就用库里的图。

        只按**名字完全相等**查，不做模糊匹配：猜错一张图比空着更糟。
        """
        wanted = str(name or "").strip()
        if not wanted:
            return ""
        from .... import library
        index = getattr(self, "_library_icon_names", None)
        if index is None:
            index = {}
            for entry in library.pictures("monster"):
                texts = [library.display_name(entry)]
                texts += list(entry.get("names") or [])
                texts += list(entry.get("aliases") or [])
                for text in texts:
                    text = str(text or "").strip()
                    if text and text not in index:
                        index[text] = str(entry.get("id") or "")
            self._library_icon_names = index
        entry_id = index.get(wanted) or ""
        return library.url_of(entry_id) if entry_id else ""

    @Slot(result=int)
    def monsterIconMaxSide(self) -> int:
        """素材库里最大一张图的边长（像素）。

        用户："所有缩略图必须以相同比例等比例放大或缩小，禁止出现图显示不全" ——
        界面拿这个值算一个统一的缩放倍数，所有格子按同一个倍数摆，谁都不会被切。
        """
        from .... import library
        side = 0
        for entry in library.pictures("monster"):
            side = max(side, int(entry.get("width") or 0),
                       int(entry.get("height") or 0))
        return side

    @Slot(result="QVariantList")
    def itemChoices(self) -> list:
        """「＋ 加资源」的候选：**一个图标一条**，带上默认效果。

        用户 2026-10-28："这地图下得加资源都是什么乱七八糟的，我应该明确指定过
        有哪些吧" —— 候选就是 `iteminfo.choices()`（`assets/items/map.json` 里
        owner 指定过的那些），别的东西不往这儿塞；效果从道具表带出来。
        """
        from ....game import iteminfo
        out = []
        for entry in iteminfo.choices():
            stem = str(entry.get("icon") or "")
            if not stem or not iteminfo.icon_exists(stem):
                continue        # 映射还在、图没了（换机器/清过 assets）就别列出来
            out.append({
                "name": str(entry.get("name") or stem),
                "icon": stem,
                "effect": str(entry.get("effect") or ""),
            })
        return out

    # ---- 怪物：添加 / 修改 / 删除 ----
    # 按模板加一只怪：模板来自「＋」弹出的下拉（第一行是空白模板）。
    # icon 是模板的缩略图（file:// URL）：选了模板就应该带着图，不能让列表里出现没图的怪。
