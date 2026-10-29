"""怪物模板库与技能：读 SQLite 模板、技能解析、用户上传的缩略图。"""

import json
import os
import re

from ..constants import _ASSETS, _SESSION


def _import_icon(source, prefix: str) -> str:
    """把用户挑的本地图片收进 `assets/uploads/`，返回 file:// URL。

    用户上传的图**不是素材库的东西**（用户："monster_icons为什么不删？" 之后
    素材库只剩 `assets/library/monster/` 一处），所以单独放 uploads。
    source 可能是 "file:///C:/..." 或纯路径；不是图片就返回空串。
    **只缩不放**：长边超过 64 就缩到 64（上传的常常是整张截图，原样塞进
    assets 又大又糊在 20px 的行里也看不出来）。
    """
    text = str(source or "").strip()
    if not text:
        return ""
    if text.lower().startswith("file://"):
        text = text[7:]
        # file:///C:/x 会多一个斜杠
        if text.startswith("/") and len(text) > 2 and text[2] == ":":
            text = text[1:]
        text = text.replace("/", os.sep)
    if not os.path.isfile(text):
        return ""
    try:
        import cv2
        import numpy as np

        with open(text, "rb") as handle:
            raw = handle.read()
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8),
                             cv2.IMREAD_UNCHANGED)
    except Exception:
        return ""
    if image is None or getattr(image, "size", 0) == 0:
        return ""
    try:
        height, width = image.shape[:2]
        long_side = max(height, width)
        if long_side > 64:
            scale = 64.0 / long_side
            image = cv2.resize(
                image,
                (max(1, int(round(width * scale))),
                 max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".png", image)
        if not ok:
            return ""
        folder = os.path.join(_ASSETS, "uploads")
        os.makedirs(folder, exist_ok=True)
        stem = os.path.splitext(os.path.basename(text))[0]
        clean = re.sub(r"[^0-9A-Za-z_\-]+", "_", stem)[:24] or "upload"
        target = os.path.join(folder, "%s_%s_%s.png" % (
            prefix, _SESSION, clean))
        buf.tofile(target)
        return "file:///" + target.replace("\\", "/")
    except Exception:
        return ""

def _skill_params(raw) -> dict:
    """技能参数的规整：开关留 bool，数字一律转成字符串（QML 一路按字符串传）。"""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            continue
        if isinstance(value, bool):
            out[name] = value
        elif value is None:
            out[name] = ""
        else:
            out[name] = str(value).strip()
    return out

def _skill_items_from_text(text: str) -> list:
    """老的技能写法（"先攻 连击" 空格分隔）→ [{name, value, code, params}]。"""
    out = []
    for token in re.split(r"[\s,，、/;；]+", (text or "").strip()):
        if token:
            out.append({"name": token, "value": "", "code": "", "params": {}})
    return out

def _parse_skill_payload(payload: str) -> list:
    """QML 传来的技能：

    新格式是 JSON 数组，一项一个技能：
    `[{"name":"破甲","value":"","code":"7","params":{"defValue":"50"}}, ...]`

    - `name` 是技能名（手册/塔里的叫法）；
    - `code` 是引擎里的技能号，**算伤害靠它**；
    - `params` 是这个技能自己的数值（破甲是 defValue，吸血是 value+add……），
      键名来自 assets/skill_params.json，别把数字塞进文本里；
    - `custom` + `effect` 只给"自定义技能"（手册里没有那种）：手册里查得到的
      介绍是用 `skillinfo` 现查的、不存盘，用户自己写的这句只能存下来
      （用户："自定义怎么只能写技能名称不能写技能介绍"）。
    老格式是空格分隔的名字串，照旧解析成空值。
    """
    text = (payload or "").strip()
    if text.startswith("["):
        try:
            data = json.loads(text)
        except Exception:
            return []          # 看着像 JSON 又坏了：宁可当没有，也别把乱码当技能名
        if isinstance(data, list):
            items = []
            seen = set()
            for row in data:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                item = {"name": name,
                        "value": str(row.get("value") or "").strip(),
                        "code": str(row.get("code") or "").strip(),
                        "params": _skill_params(row.get("params"))}
                if row.get("custom"):
                    item["custom"] = True
                    effect = str(row.get("effect") or "").strip()
                    if effect:
                        item["effect"] = effect
                items.append(item)
            return items
    return _skill_items_from_text(text)

def _monster_skill_items(monster) -> list:
    """取一只怪的技能列表。

    - 有 skill_items 就用它（数值/参数是这只怪自己的）；
    - 没有、或者是空的，就从老的 skills 串现拆一份（参数留空），
      这样旧数据也能"一行一个"地显示。
    """
    if not isinstance(monster, dict):
        return []
    items = monster.get("skill_items")
    if isinstance(items, list):
        clean = []
        for i in items:
            if not isinstance(i, dict) or not i.get("name"):
                continue
            row = {"name": str(i.get("name") or ""),
                   "value": str(i.get("value") or ""),
                   "code": str(i.get("code") or ""),
                   "params": _skill_params(i.get("params"))}
            effect = str(i.get("effect") or "").strip()
            if effect:
                row["effect"] = effect
            if i.get("custom"):
                row["custom"] = True
            clean.append(row)
        if clean:
            return clean
    return _skill_items_from_text(monster.get("skills") or "")

def _skill_names(items) -> str:
    return " ".join(str(i.get("name") or "") for i in items if i.get("name"))

def _fill_skill_codes(items) -> list:
    """把技能名对应的引擎 code 补上（算伤害的键）；已有的不动。

    code 不由界面传：界面只认名字，code 是表里查出来的，换塔/改名时以表为准。
    """
    from ...game import skillinfo
    out = []
    for item in items or []:
        row = dict(item)
        if not row.get("code"):
            row["code"] = skillinfo.code_for(row.get("name"))
        out.append(row)
    return out

def _library_order() -> dict:
    """素材库的显示顺序：文件名 → 下标。

    「＋ 加怪」下拉里的图标就是素材库里那张，**顺序也得跟素材库（文件编号）走** ——
    用户逐张核对过编号，下拉里按老 seq 排会出现"图的编号乱跳"（用户："修改图片的
    资源库的排序和文件排序不一致"）。
    """
    try:
        from ... import library
        shown = library.pictures("monster")
    except Exception:
        return {}
    order = {}
    for index, entry in enumerate(shown):
        base = os.path.basename(str(entry.get("path") or ""))
        if base:
            order[base] = index
    return order


def _sort_by_library(rows) -> list:
    """按素材库顺序排；素材库里没有那张家（没图 / 并掉了）的按原来的 seq 排最后。"""
    order = _library_order()
    if not order:
        return rows
    for row in rows:
        base = os.path.basename(str(row.get("icon") or ""))
        row["_lib"] = order.get(base)
    rows.sort(key=lambda row: (row["_lib"] is None,
                               row["_lib"] if row["_lib"] is not None else 0,
                               row.get("seq") or 0))
    for row in rows:
        row.pop("_lib", None)
    return rows


def _load_templates_from_db(path: str):
    """从 SQLite 模板库取（tools/build_monster_db.py 建的），读不了返回 None。

    库里 rows 本来按强弱排（seq），但图标已经指到**重排过编号**的素材库上，
    两边顺序不一致 → 出去之前按素材库顺序再排一次（`_sort_by_library`）。
    字段都是整数，QML 那边一路按字符串传（addMonsterTpl 收的是 str），这里统一转成字符串。
    """
    if not os.path.exists(path):
        return None
    try:
        import sqlite3
        conn = sqlite3.connect(path)
        try:
            rows = conn.execute(
                "SELECT name, hp, atk, def, exp, icon, seq, power, aliases,"
                " skills, family FROM enemy ORDER BY seq").fetchall()
        finally:
            conn.close()
    except Exception as exc:
        from ... import trace
        trace.note("templates.db_failed", error=repr(exc)[:160])
        return None
    base = "file:///" + _ASSETS.replace("\\", "/") + "/"
    out = []
    for (name, hp, atk, def_, exp, icon, seq, power, aliases, skills,
         family) in rows:
        if not name:
            continue
        try:
            alias_list = json.loads(aliases or "[]")
        except Exception:
            alias_list = []
        icon = (icon or "").strip().replace("\\", "/")
        out.append({
            "name": str(name),
            "hp": str(hp if hp is not None else ""),
            "atk": str(atk if atk is not None else ""),
            "def": str(def_ if def_ is not None else ""),
            "exp": str(exp if exp is not None else ""),
            "skills": "",
            "seq": int(seq or 0),
            "power": int(power or 0),
            "aliases": [str(a) for a in alias_list if a],
            "skills": str(skills or ""),
            "family": str(family or ""),
            "icon": base + icon if icon else "",
        })
    if not out:
        return None
    return _sort_by_library(out)

def _load_skill_catalog() -> list:
    """技能目录：`assets/monster_templates.db` 的 `skill` 表（两座塔 specials 表合并）。

    顺序按游戏里的特殊码从小到大排（先攻、坚固、连击……），界面下拉就照这个顺序列。
    """
    path = os.path.join(_ASSETS, "monster_templates.db")
    if not os.path.exists(path):
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(path)
        try:
            rows = conn.execute(
                "SELECT name FROM skill ORDER BY code_min, name").fetchall()
        finally:
            conn.close()
    except Exception as exc:
        from ... import trace
        trace.note("skills.db_failed", error=repr(exc)[:160])
        return []
    return [str(row[0]) for row in rows if row and row[0]]

def _load_monster_templates() -> list:
    """常见怪物模板：优先读 assets/monster_templates.db（有编号、按强弱排、按图去重）。

    没有库（或者库读坏了）就退回 assets/monster_templates.json —— 那是建库前的
    老数据，按名字排、没有编号，只保证界面不至于变空。
    每项里的 icon 是相对 assets 的路径，这里转成 file:// URL 给 QML 用。
    """
    rows = _load_templates_from_db(os.path.join(_ASSETS, "monster_templates.db"))
    if rows:
        return rows
    path = os.path.join(_ASSETS, "monster_templates.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    base = "file:///" + _ASSETS.replace("\\", "/") + "/"
    out = []
    for position, item in enumerate(data, start=1):
        if not isinstance(item, dict) or not item.get("name"):
            continue
        entry = dict(item)
        icon = (entry.get("icon") or "").strip().replace("\\", "/")
        entry["icon"] = base + icon if icon else ""
        entry["seq"] = position
        out.append(entry)
    return _sort_by_library(out)
