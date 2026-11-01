"""资源的默认效果/图标/排序：读 `assets/item_effects.json` + `assets/item_catalog.json`。

两张表都是工具从两座塔的 `project/items.js` 解析出来的：
- `item_effects.json`：血瓶/宝石八件（按图标存，`tools/build_item_effects.py`）；
- `item_catalog.json`：**全部道具**（钥匙、剑、盾、书、特殊道具……）
  （`tools/build_item_icons.py`，图标切到 `assets/items/<塔>_<id>.png`）。

所以"魔塔里什么道具什么效果/长什么样"这事儿不用问用户 —— 直接查表填上，
用户仍可改（不同塔的同一件道具效果可能不一样）。
"""

import io
import json
import os
import re

from ..paths import ROOT as _ROOT
_EFFECTS_PATH = os.path.join(_ROOT, "assets", "item_effects.json")
_CATALOG_PATH = os.path.join(_ROOT, "assets", "item_catalog.json")
_MAP_PATH = os.path.join(_ROOT, "assets", "items", "map.json")
_ITEMS_DIR = os.path.join(_ROOT, "assets", "items")

# 资源图标以前叫别的游戏工程目录名（`xinxin2_redKey`）或塔 key（`h5_redKey`），
# 现在一律用语义名（`key_red` / `sword` / `shield`），文件名里不再有塔/引擎的痕迹。
# 老存档、老日志里躺着旧名字，读的时候在 `migrate_icon()` 里过一道。
_RENAMED_ICONS = {
    "xinxin2_redKey": "key_red", "h5_redKey": "key_red",
    "xinxin2_blueKey": "key_blue", "h5_blueKey": "key_blue",
    "xinxin2_yellowKey": "key_yellow", "h5_yellowKey": "key_yellow",
    "xinxin2_sword1": "sword", "h5_sword1": "sword",
    "xinxin_sword1": "sword", "rm_sword1": "sword",
    "xinxin2_shield1": "shield", "h5_shield1": "shield",
    "xinxin_shield1": "shield", "rm_shield1": "shield",
}

_CACHE = {}


def migrate_icon(stem: str) -> str:
    """旧图标名 → 现在的语义名（不认识的照原样返回）。"""
    return _RENAMED_ICONS.get(str(stem or ""), str(stem or ""))


def icon_exists(stem: str) -> bool:
    """这张资源图在不在（不在就别往界面上贴空图）。"""
    text = str(stem or "").strip()
    if not text:
        return False
    return os.path.exists(os.path.join(_ITEMS_DIR, text + ".png"))


def icon_map() -> dict:
    """用户指定的"资源名 → 图标名"（assets/items/map.json）。"""
    try:
        stamp = os.path.getmtime(_MAP_PATH)
    except OSError:
        return {}
    if _CACHE.get("icon_stamp") == stamp:
        return _CACHE.get("icon_map") or {}
    data = {}
    try:
        with open(_MAP_PATH, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = {str(key).strip(): str(value).strip()
                    for key, value in loaded.items()}
    except Exception:
        data = {}
    _CACHE["icon_stamp"] = stamp
    _CACHE["icon_map"] = data
    return data


def save_icon_map(name: str, stem: str) -> None:
    """把"某个资源用哪张图"写进 map.json。"""
    path = _MAP_PATH
    data = dict(icon_map())
    data[str(name).strip()] = str(stem).strip()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
    _CACHE.pop("icon_stamp", None)
    _CACHE["icon_map"] = data


# ---- 全部道具（钥匙/剑/盾/书/特殊道具）----
def catalog() -> dict:
    """`{图标名: {name, effect, cls}}`（`tools/build_item_icons.py` 生成）。"""
    try:
        stamp = os.path.getmtime(_CATALOG_PATH)
    except OSError:
        return {}
    if _CACHE.get("catalog_stamp") == stamp:
        return _CACHE.get("catalog") or {}
    data = {}
    try:
        with io.open(_CATALOG_PATH, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = {str(key): value for key, value in loaded.items()
                    if isinstance(value, dict)}
    except Exception:
        data = {}
    _CACHE["catalog_stamp"] = stamp
    _CACHE["catalog"] = data
    # 同一件东西两座塔各有一份 → 按名字只留先遇到的那个（排序稳定）
    by_name = {}
    for stem in sorted(data):
        name = str(data[stem].get("name") or "").strip()
        if name and name not in by_name:
            by_name[name] = stem
    _CACHE["catalog_by_name"] = by_name
    return data


def catalog_by_name() -> dict:
    catalog()
    return _CACHE.get("catalog_by_name") or {}


# ---- 排序：按 owner 定的顺序来（宝石 → 武器 → 防具 → 血瓶 → 钥匙 → 其他）----
# 用户 2026-10-27 深夜："地图界面的资源要按宝石（红蓝绿黄）武器防具血瓶钥匙排序"
# —— 宝石排第一（红蓝绿黄），钥匙排最后。
KIND_LABELS = ("宝石", "武器", "防具", "血瓶", "钥匙", "其他")
# 宝石按玩家最关心的四色：红 → 蓝 → 绿 → 黄（其余颜色按老规矩兜底）
_GEM_COLOUR = (("红", 0), ("赤", 0), ("蓝", 1), ("青", 1), ("绿", 2),
               ("黄", 3), ("金", 4), ("紫", 5), ("铁", 6), ("魔", 7))
# 其它类（武器/防具/血瓶/钥匙）沿用老规矩：黄 → 蓝 → 红 → 绿 → 铁 → 魔
_COLOR_RANK = (("黄", 0), ("金", 0), ("蓝", 1), ("青", 1), ("紫", 1),
               ("红", 2), ("赤", 2), ("绿", 3), ("铁", 4), ("魔", 5))
_KIND_WORDS = (
    (0, ("宝石", "水晶", "珠子", "gem")),
    (1, ("剑", "刀", "斧", "杖", "sword", "wand")),
    (2, ("盾", "甲", "衣", "头盔", "shield", "armor")),
    (3, ("血瓶", "药水", "伤药", "药", "瓶", "potion")),
    (4, ("钥匙", "匙", "key")),
)


# ---- 四色宝石（红/蓝/绿/黄）：伤害计算那栏必须列出来 ----
# 用户："资源（包含 4 色宝石）" —— 绿宝石加的是敏捷，算式里没有敏捷这一项，
# 但它是"资源"里玩家一定会拿来算的东西，不许因为算不出加成被过滤掉。
GEM_STEMS = ("gem_red", "gem_purple", "gem_green", "gem_yellow")


def is_gem(stem: str) -> bool:
    return str(stem or "") in GEM_STEMS


def is_potion(stem: str = "", name: str = "") -> bool:
    """是不是血瓶（红蓝绿黄都算一瓶）。

    图标优先（`potion_red` 这种素材名），没有图标名才按名字查一次 ——
    和 `_merge_potions` 认"血瓶"用的是同一个口径。
    """
    value = str(stem or "")
    if value.startswith("potion_"):
        return True
    if value:
        return False
    return icon_for(name).startswith("potion_")


def kind_rank(name: str = "", icon: str = "", cls: str = "") -> int:
    """资源属于哪一类（返回 KIND_LABELS 的下标）。"""
    text = "%s %s" % (str(name or ""), str(icon or ""))
    low = text.lower()
    for rank, words in _KIND_WORDS:
        for word in words:
            if word.lower() in low:
                return rank
    if str(cls or "") == "equips":
        return 1                      # 认不出但标了装备：当武器（排防具前面）
    return len(KIND_LABELS) - 1


def _color_rank(name: str, kind: int = -1) -> int:
    """同类里的颜色次序：宝石是红蓝绿黄，其它类沿用黄蓝红绿。"""
    text = str(name or "")
    table = _GEM_COLOUR if kind == 0 else _COLOR_RANK
    for word, rank in table:
        if word in text:
            return rank
    return 9


def _magnitude(effect: str) -> int:
    """效果里最大的那个数（血瓶 150 < 400 < 2000），用来同类里从弱到强。"""
    numbers = [int(match) for match in re.findall(r"\d+", str(effect or ""))]
    return max(numbers) if numbers else 0


def sort_key(name: str = "", icon: str = "", effect: str = "",
             cls: str = "") -> tuple:
    kind = kind_rank(name, icon, cls)
    return (kind, _color_rank(name, kind), _magnitude(effect), str(name or ""))


def sort_items(items) -> list:
    """把一层里的资源按习惯顺序排好（不动别的字段）。"""
    rows = [dict(item) for item in (items or []) if isinstance(item, dict)]
    return sorted(rows, key=lambda item: sort_key(
        item.get("name", ""), item.get("icon", ""),
        item.get("effect", ""), _cls_of(item)))


def _cls_of(item: dict) -> str:
    stem = str(item.get("icon") or "")
    entry = catalog().get(stem) or {}
    return str(entry.get("cls") or "")


def _named_icon(name: str) -> str:
    """用户指定（`assets/items/map.json`）→ 全部道具表，**按名字精确对上**才算。

    返回空串 = 名字这两张表里都没有（后面还有颜色规则 / 种类兜底）。
    表里的图可能已经被清掉了（`assets/items/` 只留了用得到的那几张），
    没有文件就当没查到 —— 否则界面上会去开一张 404 的图，等于没图。
    """
    text = str(name or "").strip()
    picked = icon_map().get(text, "")
    if picked and icon_exists(picked):
        return picked
    stem = catalog_by_name().get(text, "") or ""
    return stem if stem and icon_exists(stem) else ""


def _colour_icon(text: str) -> str:
    """只有"颜色 + 种类"的名字（红药水 / 蓝宝石）：按颜色给图，认不出给空串。"""
    palette = (("红", "red"), ("赤", "red"), ("蓝", "purple"), ("紫", "purple"),
               ("绿", "green"), ("青", "green"), ("黄", "yellow"), ("金", "yellow"))
    color = ""
    for key, value in palette:
        if key in text:
            color = value
            break
    if not color:
        return ""
    if any(word in text for word in ("血瓶", "药水", "药", "瓶")):
        return "potion_%s" % color
    if any(word in text for word in ("宝石", "水晶", "钻")):
        return "gem_%s" % color
    return ""


# 只有种类、名字对不上任何表时的兜底图（两座塔里剑/盾各一张语义图）
_KIND_ICONS = {1: "sword", 2: "shield"}


def icon_for(name: str) -> str:
    """按名字挑图标：用户指定 → 全部道具表 → 颜色规则 → **种类兜底**。

    （用户："资源里资源种类不全怎么没有武器和防具还有钥匙" —— 塔里的道具表现在
    全导进来了，改名/加资源时按名字就能找到钥匙、剑、盾的图。）

    种类兜底是给"表里没有的剑/盾"用的：模型读出来是「长剑」「钢盾」「剑」「盾」
    这种没颜色、道具表里也没有的名字，以前一律空图（用户："我用刷新读取的剑和
    盾怎么没有缩略图"）。有剑/盾的语义图就先用上，数值仍然留给人自己改。
    """
    text = str(name or "").strip()
    picked = _named_icon(text)
    if picked:
        return picked
    coloured = _colour_icon(text)
    if coloured:
        return coloured
    fallback = _KIND_ICONS.get(kind_rank(text), "")
    return fallback if fallback and icon_exists(fallback) else ""


def key_for(name: str) -> str:
    """同一种资源的"身份"：能查到图标就按图标，否则按名字。

    用户："我二次刷新时，地图的怪和资源会累计" —— 模型这次叫「红药水」、
    下次叫「红血瓶」，其实都是 potion_red 那一瓶；按名字合并就会越刷越多。
    按图标归一以后，同一瓶只占一行，数量按这次读到的更新。

    **种类兜底那张图不参与归一**：长剑和钢剑都兜底成 `sword`，但它们是两件东西，
    按图合并会把两把剑并成一行、数量也串（和"红药水=红血瓶"不是一回事）。
    所以这里只认"名字精确对上"和"颜色规则"这两条。
    """
    text = str(name or "").strip()
    if not text:
        return ""
    stem = _named_icon(text) or _colour_icon(text)
    if stem:
        return "icon:" + stem
    return "name:" + "".join(text.split())


def _load():
    if "effects" in _CACHE:
        return _CACHE["effects"], _CACHE["names"]
    effects = {}
    names = {}
    try:
        with io.open(_EFFECTS_PATH, encoding="utf-8") as handle:
            effects = json.load(handle)
        if not isinstance(effects, dict):
            effects = {}
    except Exception:
        effects = {}
    try:
        with io.open(_MAP_PATH, encoding="utf-8") as handle:
            mapping = json.load(handle)
        if isinstance(mapping, dict):
            for name, stem in mapping.items():
                names.setdefault(str(stem), str(name))
                names["name:" + str(name)] = str(stem)
    except Exception:
        mapping = {}
    _CACHE["effects"] = effects
    _CACHE["names"] = names
    return effects, names


def normalize_effect(text: str) -> str:
    """把 "生命+2000" 规整成 "生命 +2000"（纯显示用）。"""
    import re
    out = str(text or "").strip()
    if not out:
        return ""
    out = re.sub(r"\s*[+＋]\s*", " +", out)
    # 连着两个加号只留一个：数值框清空再填会拼出 "攻击力 + +1"，
    # 界面上"属性"后面自己还会画一个加号，用户看到的就是两个（2026-10-28）
    out = re.sub(r"[+＋](?:\s*[+＋])+", "+", out)
    return re.sub(r"\s+", " ", out).strip()


# 效果里的"数值"：末尾那截带符号的数字，允许"万/亿/千"
_EFFECT_VALUE = re.compile(r"^(.*?)\s*([+\-＋])\s*([\d.]+)\s*([万亿千]?)\s*$")


def split_effect(text: str) -> tuple:
    """把效果拆成「属性 + 数值」：`"攻击力 +2"` → `("攻击力", "+2")`。

    用户："宝石加的属性要写死，加的数值要能改" —— 属性那半截由道具表定
    （攻击力/防御力/生命…），数值才是按这座塔要改的东西。
    没有数值的（"可以打开一扇黄门"）第二项给空串。

    多段效果（`"攻击力 +1 · 防御力 +1 · 魔防 +2"`，黄宝石那种）**整句不拆**：
    一个框只能改一个数，拆开会把另外两段写坏，所以整句当属性显示、没有数值框。
    """
    out = normalize_effect(text)
    if not out:
        return "", ""
    if "·" in out:
        return out, ""
    found = _EFFECT_VALUE.match(out)
    if not found:
        # 清空数值后的残句（"攻击力 +"）也把加号去掉：界面上加号是单独画的一个字
        return re.sub(r"\s*[+\-＋]\s*$", "", out), ""
    label = found.group(1).strip()
    # 属性那半截不该自带加号（加号是界面上单独画的一个字）：
    # "攻击力 +" 这种清空数值后的残句，再填数字就会变成两个加号
    label = re.sub(r"\s*[+\-＋]\s*$", "", label)
    if not label:
        return out, ""
    sign = "+" if found.group(2) in "+＋" else "-"
    return label, sign + found.group(3) + found.group(4)


def join_effect(label: str, value: str) -> str:
    """`("攻击力", "5")` → `"攻击力 +5"`；数值带不带符号都行（"-3" 也认）。"""
    head = str(label or "").strip()
    # 属性尾巴上残留的加号先去掉：不然拼出来是 "攻击力 + +5"
    head = re.sub(r"\s*[+\-＋]\s*$", "", head)
    number = str(value or "").strip().replace("＋", "+").replace(" ", "")
    if number == "":
        return head
    if number[0] not in "+-":
        number = "+" + number
    return (head + " " + number).strip()


# ---- 多段效果（黄宝石那种一下加三样）----
# 塔里两种分隔写法都见过：`攻击力 +1 · 防御力 +1`（item_effects.json）和
# `生命 +1000 × 攻击 +6`（游戏原文）。都当"一段一段"处理。
MULTI_SEPS = ("·", "×")


def multi_sep(text: str) -> str:
    """这段效果用的分隔符（单段给空串）。"""
    for sep in MULTI_SEPS:
        if sep in str(text or ""):
            return sep
    return ""


def _one_part(text: str) -> tuple:
    label, amount = split_effect(text)
    sign = amount[:1] if amount[:1] in ("+", "-") else ""
    digits = amount[len(sign):] if sign else amount
    return (label, sign, digits)


def split_effect_parts(text: str) -> list:
    """把效果拆成若干段 `(属性, 加减号, 数字)`，**每一段都能单独改数值**。

    `"攻击力 +1 · 防御力 +1 · 魔防 +2"` → `[("攻击力","+","1"), ...]`
    （用户 2026-10-28："黄宝石每个值都要能改"）
    """
    out = normalize_effect(text)
    if not out:
        return []
    sep = multi_sep(out)
    if not sep:
        return [_one_part(out)]
    parts = []
    for chunk in out.split(sep):
        chunk = chunk.strip()
        if chunk:
            parts.append(_one_part(chunk))
    return parts


def join_effect_parts(parts, sep: str = " · ") -> str:
    """把若干段拼回一个效果字符串（和 `split_effect_parts` 互逆）。"""
    chunks = []
    for label, sign, digits in parts:
        head = str(label or "").strip()
        amount = str(digits or "").strip()
        if amount:
            chunks.append(join_effect(head, str(sign or "+") + amount))
        elif head:
            chunks.append(head)
    return sep.join(chunks)


def effect_with_part(text: str, index: int, value: str) -> str:
    """只改第 `index` 段的数值，其余段原样留着（每段一个框，改哪段只动哪段）。"""
    parts = split_effect_parts(text)
    if not (0 <= int(index) < len(parts)):
        return normalize_effect(text)
    sep = multi_sep(text) or " · "
    label, sign, _old = parts[int(index)]
    parts[int(index)] = (label, sign or "+", str(value or "").strip())
    return join_effect_parts(parts, " %s " % sep)


def choices() -> list:
    """给「＋ 加资源」用的列表：**只列 owner 指定过的那些**（一个图标一条）。

    用户 2026-10-28："这地图下得加资源都是什么乱七八糟的，我应该明确指定过有
    哪些吧"。以前这里除了表和 map.json，还把 `item_catalog.json`（**新新魔塔1/2
    两座别的塔**的全部 99 件道具：宝石锄头、深红(Z3)、圣锤……）整表并进下拉，
    76 条里一大半和正在打的这座塔无关。

    所以"有哪些资源"只有一处来源：`assets/items/map.json`（owner 自己指定的
    "资源名 → 图标"）。`item_effects.json` / `item_catalog.json` 只用来**查**
    默认效果和图标（`effect_for` / `icon_for`），不再往下拉里塞条目。
    血瓶仍然合并成一条（红蓝绿黄都是加血，用户："红蓝黄都是加血没必要3个"）。
    """
    out = []
    seen = set()
    for name, stem in icon_map().items():
        text = str(name or "").strip()
        icon = str(stem or "").strip()
        if not text or not icon or icon in seen:
            continue
        seen.add(icon)
        out.append({"name": text, "icon": icon,
                    "effect": effect_for(icon, text),
                    "source": "", "alternatives": [],
                    "cls": _cls_of({"icon": icon})})
    rows = _merge_potions(out)
    return sorted(rows, key=lambda row: sort_key(
        row.get("name", ""), row.get("icon", ""), row.get("effect", ""),
        row.get("cls", "")))


def _merge_potions(rows: list) -> list:
    """血瓶不分颜色：红/蓝/黄/绿都是加血，选项里只留一条。

    为什么：道具表是两座塔合并来的，potion_* 的数值和单位（体力/生命）都不统一，
    列成三四条只会让人挑不出区别（用户："红蓝黄都是加血没必要3个"）。
    具体回多少在那一行里改效果；地图读到的颜色名字仍然照旧记录。
    """
    potions = [row for row in rows
               if str(row.get("icon") or "").startswith("potion_")]
    if not potions:
        return rows
    others = [row for row in rows
              if not str(row.get("icon") or "").startswith("potion_")]
    # 合并出来的那条固定用红血瓶的图：别的塔的绿瓶/黄瓶图标语义不一样，
    # 拿它当"血瓶"会把"红血瓶"的默认图改掉
    first = next((row for row in potions if row.get("icon") == "potion_red"),
                 potions[0])
    # 顺序：宝石等在前，血瓶放最后（别按 Unicode 排，中文排出来看着是乱序）
    # 默认效果用红血瓶那张表里的（"体力 +150"）—— 别写"回血"这种没数字的，
    # 伤害计算靠 `battle.parse_item_effect` 认"体力/生命 +N"，"回血"认不出来
    # 就整瓶被过滤掉（用户："拾取的血瓶没有生效"）。具体回多少仍可在行里改。
    others.append({"name": "血瓶", "icon": first.get("icon") or "potion_red",
                   "effect": first.get("effect") or "体力 +150",
                   "source": "", "alternatives": []})
    return others


# 武器/防具的默认值都是 0：具体加多少是"这一座塔"的事，由用户在那行里填。
# （用户 2026-10-28："武器和防具的默认值都是0"）
EQUIP_DEFAULT_VALUE = "0"
_EQUIP_EFFECT = {1: "攻击力 +", 2: "防御力 +"}      # 1 = 武器，2 = 防具


def _equip_kind(stem: str = "", name: str = "") -> int:
    """这件资源是武器(1)/防具(2)/都不是(0)：按图标和名字认，和排序同一套规矩。"""
    stem = str(stem or "").strip()
    entry = catalog().get(stem) or {}
    text = str(name or "").strip() or str(entry.get("name") or "")
    kind = kind_rank(text, stem, str(entry.get("cls") or ""))
    return kind if kind in (1, 2) else 0


def effect_for(stem: str = "", name: str = "") -> str:
    """按图标（优先）或名字查默认效果；查不到给空串。

    武器/防具一律给 0（`攻击力 +0` / `防御力 +0`）—— 表里那两件是**别的塔**
    解析来的（铁剑 +10），照抄过来会把这座塔的数值写错。
    """
    kind = _equip_kind(stem, name)
    if kind:
        return _EQUIP_EFFECT[kind] + EQUIP_DEFAULT_VALUE
    effects, names = _load()
    if stem and stem in effects:
        return normalize_effect(effects[stem].get("effect", ""))
    if stem:
        entry = catalog().get(stem) or {}
        if entry.get("effect"):
            return normalize_effect(entry["effect"])
    if name:
        mapped = names.get("name:" + str(name))
        if mapped and mapped in effects:
            return normalize_effect(effects[mapped].get("effect", ""))
        catalog_stem = catalog_by_name().get(str(name), "")
        entry = catalog().get(catalog_stem) or {}
        if entry.get("effect"):
            return normalize_effect(entry["effect"])
    return ""
