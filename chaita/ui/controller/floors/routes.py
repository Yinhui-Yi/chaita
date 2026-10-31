"""路线链：地图上拖出来的一条路线（走过哪些格），每格再填"这一格有什么"。

用户："长按玩家起步、拖过红线，松手生成一条交互路线"（`docs/ROUTE.md`）。
路线存在**那一层的记录里**（`entry["routes"]`），跟怪/资源一起随会话保存 ——
每格填的怪/资源是用户手点的，重启就丢等于白点。

一条路线长这样：
    {"at": "17:20", "cells": [{"row": 0, "col": 0, "kind": "monster",
                               "name": "红头怪", "hp": 80, ...}, ...]}

`cells` 按走过的顺序排，**允许重复**（回头路是必要的）。`kind` 只有三种：
monster（怪，算掉血）/ item（资源，改属性）/ door（门，不掉血）。没填的格
没有 kind —— 就是"只是走过"。计算时它们都占一格（界面上的格子不能错位），
公式里按 `battle.run_plan` 的 empty 走。

**格子上的初始内容不用手点**：刷新地图时 AI 已经把"每一格有什么"记在
`entry["grid"]["cells"]` 里了（怪 / 宝石 / 血瓶），拖完路线先把这些填进
格子；手册里有数值的怪连血量攻防技能一起带上，资源连图标效果一起带上 ——
用户可以再点格子改（改过的不会再被覆盖）。
"""

import time

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

# 一格能填的东西（空格/走过没有 kind）
KINDS = ("monster", "item", "door")

# 从界面收下来的字段：其余一律丢掉（免得把 QML 的内部东西写进记录）
FILL_FIELDS = ("kind", "name", "icon", "effect", "hp", "atk", "def",
               "count", "skills", "skillsText")

# 一层最多留几条路线：手画的，一多就翻不动了
MAX_ROUTES = 20


def _clean_cells(cells) -> list:
    """地图层交上来的格子：行列（整数）+ 可选楼层，顺序原样保留。

    跨层路线里每格记着它画在哪一层（`floor`）；同层路线没有这个字段。
    """
    out = []
    for cell in cells or []:
        if not isinstance(cell, dict):
            continue
        try:
            row = int(cell.get("row"))
            col = int(cell.get("col"))
        except (TypeError, ValueError):
            continue
        one = {"row": row, "col": col}
        floor = str(cell.get("floor") or "").strip()
        if floor:
            one["floor"] = floor
        out.append(one)
    return out


def _clean_fill(fill) -> dict:
    """一格的内容：只留认识的字段，kind 不认识就当成"清空"。

    技能只留"算伤害要的那三样"（名字 / code / 参数）：界面递进来的那份还带着
    schema（画参数格子用的），存进记录里没用，还越积越大。
    """
    if not isinstance(fill, dict):
        return {}
    kind = str(fill.get("kind") or "").strip()
    if kind not in KINDS:
        return {}
    out = {"kind": kind}
    for key in FILL_FIELDS:
        if key == "kind" or key not in fill:
            continue
        value = fill.get(key)
        if value is None or value == "":
            continue
        if key == "skills":
            cleaned = []
            for skill in value if isinstance(value, list) else []:
                if not isinstance(skill, dict):
                    continue
                name = str(skill.get("name") or "").strip()
                if not name:
                    continue
                cleaned.append({"name": name,
                                "code": str(skill.get("code") or ""),
                                "params": dict(skill.get("params") or {})})
            if cleaned:
                out[key] = cleaned
            continue
        out[key] = value
    return out


class RoutesMixin:
    @Slot(result="QVariantList")
    def routeItems(self) -> list:
        """路线链能填的资源：宝石 / 武器 / 防具 / 血瓶。

        武器/防具以前被排除（"非怪和宝石血瓶不需要显示"），但用户 2026-10-29
        改主意：武器/防具要能进路线（它们改攻防、会影响后面的掉血）。
        钥匙/书/门这类和掉血无关的仍不进。
        """
        from ....game import iteminfo
        out = []
        for row in self.battleItems():
            icon = str(row.get("icon") or "")
            kind = iteminfo.kind_rank(str(row.get("name") or ""), icon)
            if kind in (0, 1, 2, 3):   # 宝石 / 武器 / 防具 / 血瓶
                out.append(row)
        return out

    @Slot(str, "QVariantList", result=int)
    def saveRoute(self, floor_text, cells) -> int:
        """松手存一条路线，返回它在那一层里的序号（-1 = 这层不在了/没格子）。

        顺手把刷新地图时记下的"这一格有什么"填进格子：用户要的是"拖完就直接
        看见这条路上有什么怪、捡什么"，而不是一格一格手点。
        """
        cleaned = _clean_cells(cells)
        if not cleaned:
            return -1
        position, entry, routes = self._floor_routes(floor_text)
        if routes is None:
            return -1
        routes = routes + [{"at": time.strftime("%H:%M"),
                            "cells": self._with_map_content(entry, cleaned)}]
        self._store_routes(position, entry, routes)
        return min(len(routes), MAX_ROUTES) - 1

    @Slot(str, int, result="QVariantList")
    def routeCells(self, floor_text, route_index) -> list:
        """这条路线每格的**当前**内容：按格子坐标从这一层的 grid 实时取。

        用户改了 grid（编辑模式拖坐标 / 改资源数值）之后，路线链跟着变，
        不再用创建路线那一刻的快照。grid 里没有这一格时，保留格子自己的内容。
        """
        position, entry, routes = self._floor_routes(floor_text)
        if routes is None or route_index < 0 or route_index >= len(routes):
            return []
        cells = [dict(cell) for cell in (routes[route_index].get("cells") or [])
                 if isinstance(cell, dict)]
        return self._with_map_content(entry, cells)

    @Slot(str, int, int, "QVariantMap", result=bool)
    def saveRouteCell(self, floor_text, route_index, cell_index, fill) -> bool:
        """给链上第 cell_index 格填内容；空的 fill = 清掉这一格的内容。

        写完打上 `manual`：**这一格以后按链上这份显示**，不再被这一层地图记录
        同坐标的内容盖掉（用户 2026-10-31："链上改的那一份优先 但不会影响到其他地方"）。
        只动这条路线的这一格，`grid` 不碰。
        """
        position, entry, routes = self._floor_routes(floor_text)
        if not self._valid_cell(routes, route_index, cell_index):
            return False
        content = _clean_fill(fill)
        route = dict(routes[route_index])
        cells = [dict(cell) for cell in route.get("cells") or []]
        base = {"row": cells[cell_index]["row"],
                "col": cells[cell_index]["col"], "manual": True}
        floor = str(cells[cell_index].get("floor") or "")
        if floor:
            base["floor"] = floor
        base.update(content)
        cells[cell_index] = base
        route["cells"] = cells
        routes[route_index] = route
        self._store_routes(position, entry, routes)
        return True

    @Slot(str, int, str, result=bool)
    def saveRouteMemo(self, floor_text, route_index, memo) -> bool:
        """给一条路线写备注。

        默认是"走完这条路之后的血/攻/防/魔防"（用户："备注默认是玩家路线最后的
        血量攻击防御魔防"），用户可以再往里加自己的话。
        """
        position, entry, routes = self._floor_routes(floor_text)
        if routes is None or route_index < 0 or route_index >= len(routes):
            return False
        route = dict(routes[route_index])
        text = str(memo or "").replace("\r", " ").replace("\n", " ").strip()
        if text:
            route["memo"] = text
        else:
            route.pop("memo", None)
        routes[route_index] = route
        self._store_routes(position, entry, routes)
        return True

    @Slot(str, int, result=bool)
    def removeRoute(self, floor_text, route_index) -> bool:
        """删掉一条路线（整条，不是一格）。"""
        position, entry, routes = self._floor_routes(floor_text)
        if routes is None or route_index < 0 or route_index >= len(routes):
            return False
        routes = routes[:route_index] + routes[route_index + 1:]
        self._store_routes(position, entry, routes)
        return True

    # ---- 上面三件事共用的那一套：取出那一层的路线 → 改副本 → 写回去 ----

    def _entry_for(self, floor_text):
        """按层名找那一层的记录（跨层路线预填时要读别层的 grid）。"""
        target = str(floor_text or "")
        for entry in self._map_history:
            if str((entry or {}).get("floor") or "") == target:
                return entry
        return None

    def _map_content(self, entry) -> dict:
        """刷新地图时记下来的"每一格有什么"：`(row, col)` → `{kind, name}`。

        坐标在 AI 那一问里就已经换成 0 开始了（和地图层画的格子一致）。
        """
        grid = (entry or {}).get("grid") or {}
        found = {}
        for cell in grid.get("cells") or []:
            if not isinstance(cell, dict):
                continue
            try:
                row = int(cell.get("row"))
                col = int(cell.get("col"))
            except (TypeError, ValueError):
                continue
            kind = str(cell.get("kind") or "")
            name = str(cell.get("name") or "").strip()
            if kind not in ("monster", "item") or not name:
                continue
            info = {"kind": kind, "name": name}
            if kind == "item":
                info["effect"] = str(cell.get("effect") or "")
            found.setdefault((row, col), info)
        return found

    def _with_map_content(self, entry, cells) -> list:
        """把地图上记的内容填进格子（怪带数值技能、资源带图标效果）。

        只填**怪 / 宝石 / 血瓶**：用户说"非怪和宝石血瓶不需要显示"，其它东西
        （钥匙、武器、防具、书）照样记在那一层的地图记录里，但不进路线链 ——
        不然链上一排"黄/铁/书"既看不懂又和掉血无关。
        找不到记录（老截图、AI 没读到这一格）就只留坐标 —— 用户点一下自己填。
        """
        route_floor = str((entry or {}).get("floor") or "")
        # 跨层路线：每一格的内容从**它自己那一层**的地图记录里取
        cache = {}

        def content_of(floor_text):
            if floor_text not in cache:
                target = floor_text or route_floor
                if target == route_floor:
                    cache[floor_text] = self._map_content(entry)
                else:
                    cache[floor_text] = self._map_content(
                        self._entry_for(target))
            return cache[floor_text]

        monsters = {row.get("name"): row for row in self.battleMonsters()}
        out = []
        for cell in cells:
            data = dict(cell)
            # **链上亲手改过的那一格优先**（`manual`）：不再被这一层的地图记录盖掉。
            # 用户 2026-10-31："链上改的那一份优先 但不会影响到其他地方" ——
            # 只影响这一条路线的这一格，地图记录（`grid`）一个字节都不动。
            if data.get("manual"):
                out.append(data)
                continue
            hit = content_of(str(cell.get("floor") or "")).get(
                (cell["row"], cell["col"]))
            if hit is None:
                out.append(data)
                continue
            fill = {"kind": hit["kind"], "name": hit["name"]}
            if hit["kind"] == "monster":
                monster = monsters.get(hit["name"]) or {}
                # 怪的数值和技能都带上（算掉血要用）；手册里没有就只留名字
                for key in ("hp", "atk", "def", "icon", "skills",
                            "skillsText"):
                    if monster.get(key) not in (None, "", []):
                        fill[key] = monster[key]
            else:
                # 资源（宝石/武器/防具/血瓶）按道具表补图标和效果 —— 和
                # 「这一层」资源行同一套规则，不自己猜；钥匙/书不进路线
                from ....game import iteminfo
                icon = iteminfo.icon_for(hit["name"]) or ""
                kind = iteminfo.kind_rank(str(hit["name"] or ""), icon)
                if kind not in (0, 1, 2, 3):
                    out.append(data)
                    continue
                effect = (hit.get("effect")
                          or iteminfo.effect_for(icon, hit["name"]) or "")
                if icon:
                    fill["icon"] = icon
                if effect:
                    fill["effect"] = effect
            data.update(_clean_fill(fill))
            out.append(data)
        return out

    def _floor_routes(self, floor_text):
        """`(position, entry, routes)`；那一层不在就是 `(-1, None, None)`。

        序号一律先验一遍：QML 那边按下标点进来，传的号可能已经过期（层被删了、
        路线被删了）。验不过就当没发生，别把异常抛到界面上。
        """
        floor_text = str(floor_text or "")
        for position, entry in enumerate(self._map_history):
            if entry.get("floor") != floor_text:
                continue
            routes = [dict(row) for row in (entry.get("routes") or [])
                      if isinstance(row, dict)]
            return position, entry, routes
        return -1, None, None

    @staticmethod
    def _valid_cell(routes, route_index, cell_index) -> bool:
        if routes is None or route_index < 0 or route_index >= len(routes):
            return False
        cells = routes[route_index].get("cells") or []
        return 0 <= cell_index < len(cells)

    def _store_routes(self, position, entry, routes) -> None:
        updated = dict(entry)
        updated["routes"] = routes[-MAX_ROUTES:]
        self._map_history[position] = updated
        self.mapHistoryChanged.emit()
