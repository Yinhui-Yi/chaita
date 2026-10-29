"""建「怪物模板」数据库：`assets/monster_templates.db`（SQLite）。

为什么要有它（用户原话："排序不对，应该按强弱排，你要有编号，最好建一个数据库"）：

1. **强弱排序**：原来 `assets/monster_templates.json` 是按名字排的（"上级魔法师、
   不死战士、不死骷髅兵……"），看列表根本分不出谁强谁弱。现在从两座塔的
   `project/enemys.js` 重新抽出全部数值，按 `power = hp × atk` 从强到弱排 ——
   魔塔里判断一只怪难不难打，就是"它血有多厚 × 每回合咬你多疼"（打它要站着挨
   多少血）。`def` 只影响回合数，作次级排序键。
2. **编号**：排完序给每只一个 `seq`（1、2、3…），界面上显示成 `#001`。
3. **图片不能重复**：两个塔是同一套美术，"xinxin_greenSlime.png" 和
   "xinxin2_greenSlime.png" 像素完全一样，下拉里却是两行、看着像重复。这里按
   **图标 png 的 sha1** 去重（同名不同图、同图不同名都按图算），一张图只留一行，
   留下数值最强的那条，其它名字记进 `aliases`。

技能：`project/functions.js` 里 getSpecials() 那张表就是游戏的技能目录
（[码, 名字, 说明, 颜色, 标志]），每只怪的 `special` 字段就是这些码（数字或数组）。
两座塔的码表不一样（xinxin 的 4 = "2连击"，xinxin2 的 4 = "二回攻击"），所以按
**各自塔的表**翻译，名字合并进 `skill` 表，怪物→技能关系进 `enemy_skill`，
`enemy.skills` 再存一份空格分隔的字符串给界面直接用。

产物：
    assets/monster_templates.db     SQLite，表 `enemy` / `skill` / `enemy_skill`
    assets/monster_templates.json   只给 tools/build_library.py 用（icon_from → 素材库路径）
                                    （按名字找 icon），重新切图后先跑那个再跑这个

重跑方式（两座塔目录变了就重跑，id 会按图片指纹保住，seq 会重算）：

    python tools/build_monster_db.py
    python tools/build_monster_db.py <xinxin目录> <xinxin2目录>

排序口径想换只改 `SORT_KEY`（见下），别的都不用动。
"""

import glob
import hashlib
import io
import json
import os
import re
import sqlite3
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
ICONS = os.path.join(ASSETS, "library", "monster")
DB_PATH = os.path.join(ASSETS, "monster_templates.db")

HOME = os.path.expanduser("~")
DEFAULT_TOWERS = [
    os.path.join(HOME, "Downloads", "xinxin", "mota_pack_20260623_204744"),
    os.path.join(HOME, "Downloads", "xinxin2new", "xinxin2"),
]
LABELS = ["xinxin", "xinxin2"]

# 排序：**同类型的排在一起，类型之间按游戏里的出场顺序**（用户："首先应该是史莱姆，
# 然后蝙蝠……同类型的要放一起"）。templates 里怪是按家族一组组排好的（史莱姆/蝙蝠/
# 骷髅/丧尸…），所以：
#   1. 先用 key 剥掉颜色/大小/阶位这些修饰词，得到"家族"（greenSlime → slime）；
#     mod  +  camel  →  slime）
#   2. 家族的名次 = 家族里最早出现的那个怪在源文件里的位置（两座塔按 xinxin 先、
#      xinxin2 后的顺序接起来）；
#   3. 家族内部按源文件里的先后（作者自己的强弱顺序），位置相同再按血×攻、名字。
# 想换口径只动这里。
SORT_KEY = lambda r: (r["family_rank"], r["source_rank"],
                      r["hp"] * r["atk"], r["name"])  # noqa: E731

# 家族名里要去掉这些修饰词（反复剥到剥不掉为止）
FAMILY_MODIFIERS = (
    "green", "red", "black", "gold", "silver", "white", "blue", "purple",
    "yellow", "orange", "cyan", "dark", "light", "gray", "grey", "big",
    "small", "mini", "horn", "king", "lord", "man", "woman", "captain",
    "soilder", "soldier", "knight", "priest", "mage", "sword", "magic",
    "giant", "elder", "young", "high", "low", "super", "ultra", "ghost",
    "steel", "poison", "bad", "fairy",
)


# 中文名的修饰词："紫色史莱姆" → 史莱姆、"烈焰丧尸" → 丧尸、"毒龙" → 龙
NAME_PREFIX = ("绿色", "红色", "黑色", "黄色", "蓝色", "紫色", "白色", "青色", "橙色",
               "黄金", "白银", "金色", "银色", "中级", "高级", "上级", "初级",
               "不死", "剧毒", "烈焰", "寒冰", "极寒", "黑暗", "生气", "大", "小",
               "冻", "鬼", "血", "圣", "铁", "钢", "毒", "邪", "狂", "雷", "火")
NAME_SUFFIX = ("首领", "队长", "法师", "术士", "剑士", "士兵", "武士", "巫师",
               "骑士", "战士", "使者", "领主", "王", "兵", "人", "怪", "魔")

# 源数据里"名字和 id 对不上"的怪：塔作者把别人的 id 挪用了（剑神·沙士 用的
# goldSlime 这个 id，图也是史莱姆的图），自动分家族会把它们塞进史莱姆/骷髅里，
# 这里一个个钉死。
FAMILY_OVERRIDES = {
    # 名字里没有任何物种词、id 又是别人挪用的（xinxin2 拿 skeletonKing 的 id 用），
    # 只能手工钉到 boss 组（排在最后）
    "魔神·些多": "boss",
}

# 自定义 id（E300 这种）没法从 id 看家族，就按中文名里的"物种词"认：
# 毒龙 → 龙家族、紫色史莱姆 → 史莱姆家族。词按长度从长到短匹配。
SPECIES_WORDS = (
    ("史莱姆", "slime"), ("蝙蝠", "bat"), ("骷髅", "skeleton"),
    ("丧尸", "zombie"), ("僵尸", "zombie"), ("石头", "rock"), ("石怪", "rock"),
    ("魔法师", "priest"), ("法师", "priest"), ("术士", "priest"),
    ("巫师", "wizard"), ("守卫", "guard"), ("卫兵", "guard"),
    ("骑士", "knight"), ("公主", "princess"), ("妖精", "fairy"),
    ("仙子", "fairy"), ("八爪鱼", "octopus"), ("触手", "tentacle"),
    ("魔王", "king"), ("弓兵", "archer"), ("剑士", "swords"),
    ("剑兵", "swords"), ("剑王", "swords"), ("剑神", "swords"),
    ("武士", "swords"), ("战士", "soldier"), ("勇者", "hero"),
    ("天使", "angel"), ("元素", "elemental"), ("魔眼", "eye"),
    ("龙", "dragon"), ("马", "horse"),
)

# 这些名字的怪直接不进库（源数据里自己标了"已弃用"）
DEPRECATED_MARKERS = ("已弃用", "废弃", "新敌人")

# 清理统计（跑完打印一眼能看出筛掉了什么）
SKIPPED = {"no_stats": [], "no_icon": [], "anomaly": []}


# 一眼就不是正常怪的数值（塔里用它们当"打不过 / 别打"的占位）：
#   · hp ≥ 5 万：无敌/剧情怪（剑圣 999999、仙子 9999999、尖角怪 99999、黑暗妖精 100000）
#   · def ≥ 9000：根本砍不动（黄金史莱姆王 / 白银史莱姆王的 def 9999）
#   · hp ≤ 1 且 atk = 0：加进去只能显示"生命 1 攻击 0"（黄金史莱姆 / 白银史莱姆）
#   · atk ≤ 1 且 money / exp 都是 0：没有伤害也没有奖励（邪恶蝙蝠 1000/1/0）
ANOMALY = {
    "hp_max": 50000,
    "def_max": 9000,
}


def looks_placeholder(row):
    """这条模板的数值像不像"不是正常怪"的占位，像就返回原因，不像返回 ""。"""
    hp, atk, def_ = row["hp"], row["atk"], row["def"]
    money, exp = row.get("money", 0), row.get("exp", 0)
    if hp >= ANOMALY["hp_max"]:
        return "hp %d ≥ %d（无敌/剧情怪）" % (hp, ANOMALY["hp_max"])
    if def_ >= ANOMALY["def_max"]:
        return "def %d ≥ %d（砍不动）" % (def_, ANOMALY["def_max"])
    if hp <= 1 and atk == 0:
        return "hp %d / atk 0（空壳）" % hp
    if atk <= 1 and money == 0 and exp == 0:
        return "atk %d 且无金币经验（没威胁也没奖励）" % atk
    return ""


def name_stem(name):
    """紫色史莱姆 → 史莱姆；烈焰丧尸 → 丧尸；毒龙 → 龙（给 E 开头的自定义 id 用）。"""
    cur = (name or "").replace("·", "").strip()
    changed = True
    while changed:
        changed = False
        for word in NAME_PREFIX:
            if cur.startswith(word) and len(cur) - len(word) >= 2:
                cur = cur[len(word):]
                changed = True
        for word in NAME_SUFFIX:
            if cur.endswith(word) and len(cur) - len(word) >= 2:
                cur = cur[:-len(word)]
                changed = True
    return cur or name


def family_of(key):
    """greenSlime / slimelord / ghostSkeleton → slime / slime / skeleton。"""
    raw = re.sub(r"[^a-z0-9]", "", (key or "").lower())
    raw = re.sub(r"\d+$", "", raw)
    cur = raw
    changed = True
    while changed:
        changed = False
        for word in FAMILY_MODIFIERS:
            if cur.startswith(word) and len(cur) - len(word) >= 3:
                cur = cur[len(word):]
                changed = True
            elif cur.endswith(word) and len(cur) - len(word) >= 3:
                cur = cur[:-len(word)]
                changed = True
    return cur or raw or "unknown"


def load_icon_map():
    """名字 → 缩略图：从 `assets/monster_templates.json` 的 `icon_from`（塔:id:尺寸）取。

    为什么不用"<塔>_<id>.png 存在就用"：两个塔有同名的 id（比如都有 E336），
    xinxin 的 E336 是毒龙、xinxin2 的 E336 叫"新敌人"，按文件存在性硬猜会把
    毒龙的图挂到"新敌人"头上（实测过）。这里以切图脚本写进 JSON 的 icon_from
    为准，一条一条对得上。
    """
    path = os.path.join(ASSETS, "monster_templates.json")
    mapping = {}
    try:
        data = json.load(io.open(path, encoding="utf-8"))
    except Exception as exc:
        print("读不了 %s（%r），缩略图全部当没有" % (path, exc))
        return mapping
    for item in data:
        icon = (item.get("icon") or "").strip()
        source = (item.get("icon_from") or "").strip()
        if not icon or not source:
            continue
        parts = source.split(":")
        if len(parts) < 2:
            continue
        mapping[(parts[0], parts[1])] = icon
    return mapping


def parse_enemys(path):
    """enemys.js 是一坨 JS 对象字面量（键没引号），补上引号再当 JSON 解析。"""
    text = io.open(path, encoding="utf-8", errors="replace").read()
    start = text.index("{")
    body = text[start:text.rindex("}") + 1]
    body = re.sub(r'([{,])\s*([A-Za-z0-9_$]+)\s*:', r'\1"\2":', body)
    body = re.sub(r",(\s*[}\]])", r"\1", body)          # 去掉尾逗号
    return json.loads(body)


def parse_specials(proj):
    """project/functions.js 里的 getSpecials()：返回 {特殊码: 技能名}。

    形如 [26, "支援", "说明…", "#77c0b6", 1]，只取码和名字（说明里可能有函数，
    不好稳定解析），够下拉框用了。
    """
    path = os.path.join(proj, "project", "functions.js")
    if not os.path.exists(path):
        return {}
    text = io.open(path, encoding="utf-8", errors="replace").read()
    start = text.find("getSpecials")
    if start < 0:
        return {}
    ret = text.find("return", start)
    if ret < 0:
        return {}
    body = text[ret:ret + 12000]
    end = body.find("];")
    if end > 0:
        body = body[:end]
    table = {}
    for code, name in re.findall(r'\[\s*(\d+)\s*,\s*"([^"]+)"', body):
        # 整个应用的 skills 都是"空格分隔的一串"，名字里带空格会被拆成两个技能
        # （实测："BOSS Ⅰ型" 写进库后变成了 BOSS / Ⅰ型），这里直接把空格去掉
        table[int(code)] = name.replace(" ", "").replace("\u3000", "")
    return table


def special_codes(value):
    """enemy.special 可能是 null / 0 / 数字 / 数组，统一成码列表（0 不算）。"""
    if isinstance(value, list):
        out = []
        for item in value:
            try:
                code = int(item)
            except Exception:
                continue
            if code:
                out.append(code)
        return out
    try:
        code = int(value)
    except Exception:
        return []
    return [code] if code else []


def to_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def icon_file(mapping, towel_and_key):
    return mapping.get(towel_and_key, "")


# 图片指纹的缓存：icon 文件名 -> 聚类 id
_PICTURE_IDS = {}
_PICTURE_REPS = []          # [(id, shape, 像素数组)]
_PICTURE_STATS = {"merged": 0}

# 两张图标算"同一张图"的门槛：形状一致、平均通道差 ≤ 3、有差异的像素 ≤ 15%。
# 为什么不用文件 sha1：同一条素材在两座塔里被重新编码/切帧过，字节不同但画面一样
# （实测 xinxin_greenSlime 和 xinxin2_greenSlime 只有 34/304 个像素差 1）。
PIX_MEAN_MAX = 3.0
PIX_FRAC_MAX = 0.15
# 缩到同一尺寸再比的门槛。只收"几乎是同一张图"的：颜色变体（史莱姆人/水银人，
# mean≈7.5）不并，那是两只怪；中级骷髅兵/骷髅队长（mean≈1.5）、
# 黑魔王/黑衣魔王（mean≈6）这种同图不同尺寸的并掉。
SCALED_MEAN_MAX = 6.5
SCALED_FRAC_MAX = 0.6


def _load_icon(icon_name):
    path = os.path.join(ICONS, os.path.basename(icon_name))
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    return image


def _same_picture(a, b):
    """同一张图？先按原尺寸比，尺寸不同就缩到 32×32 再比（只为比较，不落盘）。

    为什么还要缩着比：同一只怪在两座塔里可能一个取 32px 帧、一个取 48px 帧，
    裁出来的图尺寸就不一样（实测 中级骷髅兵 16×19 和 骷髅队长 26×30 是同一张图）。
    """
    if a is None or b is None:
        return False
    if a.shape == b.shape:
        diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
        if (float(diff.mean()) <= PIX_MEAN_MAX
                and float((diff.sum(axis=2) > 0).mean()) <= PIX_FRAC_MAX):
            return True
    na = cv2.resize(a, (32, 32), interpolation=cv2.INTER_NEAREST)
    nb = cv2.resize(b, (32, 32), interpolation=cv2.INTER_NEAREST)
    diff = np.abs(na.astype(np.int16) - nb.astype(np.int16))
    return (float(diff.mean()) <= SCALED_MEAN_MAX
            and float((diff.sum(axis=2) > 0).mean()) <= SCALED_FRAC_MAX)


def picture_of(icon_name, name):
    """去重指纹：有图就按"画面"聚类（近似像素比较），没图按名字。

    没图的（5 只彩色史莱姆）不能按图算，只能按名字分开，否则会并成一只。
    """
    if not icon_name:
        return "noicon:" + name
    cached = _PICTURE_IDS.get(icon_name)
    if cached:
        return cached
    image = _load_icon(icon_name)
    for picture_id, _shape, rep in _PICTURE_REPS:
        if _same_picture(rep, image):
            _PICTURE_IDS[icon_name] = picture_id
            _PICTURE_STATS["merged"] += 1
            return picture_id
    picture_id = "pic:%d" % len(_PICTURE_REPS)
    _PICTURE_REPS.append((picture_id, None if image is None else image.shape, image))
    _PICTURE_IDS[icon_name] = picture_id
    return picture_id


def collect(towers, mapping):
    rows = []
    skill_pairs = []      # [(特殊码, 技能名, 塔)]：建 skill 表用
    for (label, proj) in towers:
        path = os.path.join(proj, "project", "enemys.js")
        if not os.path.exists(path):
            print("跳过（没有 enemys.js）：%s" % path)
            continue
        skill_map = parse_specials(proj)
        # 整个技能表都进目录（不只是有怪带的那几个码，不然"先攻"这种都可能漏掉）
        for code, name in skill_map.items():
            skill_pairs.append((code, name, label))
        data = parse_enemys(path)
        offset = 0 if label == LABELS[0] else 1000
        for position, (key, value) in enumerate(data.items()):
            if not isinstance(value, dict):
                continue
            name = (value.get("name") or "").strip()
            if not name:
                continue
            if any(word in name for word in DEPRECATED_MARKERS):
                continue                      # 源数据里自己标了"已弃用"的不要
            hp0 = to_int(value.get("hp"))
            atk0 = to_int(value.get("atk"))
            if hp0 == 0 and atk0 == 0:
                # 三项数值全 0 = 塔作者留的空壳（骷髅王 / 天使 / 元素生物…），
                # 加进列表只会显示"生命 0 攻击 0"，不算模板
                SKIPPED["no_stats"].append(name)
                continue
            icon = mapping.get((label, key), "")
            codes = special_codes(value.get("special"))
            skills = [skill_map[c] for c in codes if c in skill_map]

            rows.append({
                "name": name,
                "key": key,
                "tower": label,
                "towers": label,
                "hp": to_int(value.get("hp")),
                "atk": to_int(value.get("atk")),
                "def": to_int(value.get("def")),
                "money": to_int(value.get("money")),
                "exp": to_int(value.get("exp")),
                "agi": to_int(value.get("agi")),
                "cri": to_int(value.get("cri")),
                "icon": icon,
                "picture": picture_of(icon, name),
                "skills": " ".join(skills),
                "source_rank": offset + position,
                # E 开头的 id 是作者自己加的（E300、E336…），没法和别人比家族，
                # 先留空，等全量收完再按中文名认领到已有家族
                "family": "" if re.fullmatch(r"e\d+", key.lower())
                          else family_of(key),
                "aliases": "[]",
            })
    return rows, skill_pairs


def merge(rows):
    """按图片合并：一张图只留一行，取数值最强的那条，其它名字进 aliases。

    两轮：
      1. 有图的按图片 sha1 分组（同一张图的不同叫法算一只）；
      2. 没图的先看"有没有同名的行"，有就并进去（不然同一只怪会因为一份没图而
         各自留一行），彻底没图的按名字分组（5 只彩色史莱姆确实没立绘，不能合成一只）。
    """
    groups = {}      # picture -> row
    order = []       # 保持首次出现的顺序，稳定
    by_name = {}     # 名字 -> picture

    def add(picture, row):
        row = dict(row)
        row["_names"] = [row["name"]]
        row["_towers"] = [row["tower"]]
        row["_skills"] = [tok for tok in (row.get("skills") or "").split() if tok]
        row["_source_rank"] = row["source_rank"]
        row["_family"] = row["family"]
        groups[picture] = row
        order.append(picture)
        by_name[row["name"]] = picture
        return row

    for row in rows:                      # 第一轮：有图的按图片指纹分
        if not row["icon"]:
            continue
        picture = row["picture"]
        old = groups.get(picture)
        if old is None:
            add(picture, row)
            continue
        if row["name"] not in old["_names"]:
            old["_names"].append(row["name"])
            by_name[row["name"]] = picture
        if row["tower"] not in old["_towers"]:
            old["_towers"].append(row["tower"])
        first = min(old["_source_rank"], row["source_rank"])
        if row["hp"] * row["atk"] > old["hp"] * old["atk"]:
            names, towers = old["_names"], old["_towers"]
            kept = dict(row)
            kept["_names"] = names
            kept["_towers"] = towers
            kept["_skills"] = [tok for tok in (row.get("skills") or "").split()
                               if tok]
            kept["_source_rank"] = first
            kept["_family"] = old["_family"]
            groups[picture] = kept
        old["_source_rank"] = first

    for row in rows:                      # 第二轮：没图的认领同名行，认不到就自己一行
        if row["icon"]:
            continue
        picture = by_name.get(row["name"]) or ("noicon:" + row["name"])
        old = groups.get(picture)
        if old is None:
            add(picture, row)
            continue
        if row["tower"] not in old["_towers"]:
            old["_towers"].append(row["tower"])

    out = []
    for picture in order:
        row = groups[picture]
        names = row.pop("_names")
        towers = row.pop("_towers")
        row["skills"] = " ".join(row.pop("_skills"))
        row["source_rank"] = row.pop("_source_rank")
        row["family"] = row.pop("_family")
        row["aliases"] = json.dumps([n for n in names if n != row["name"]],
                                    ensure_ascii=False)
        row["towers"] = ",".join(towers)
        out.append(row)
    return out


def assign_families(rows):
    """给没有家族的怪（E 开头的自定义 id）按中文名认领到已有家族，认不到就自己一组。

    做法：把已有家族的名字都算一个"中文词根"（紫色史莱姆 → 史莱姆），做成
    词根 → 家族的票数表；再拿没家族的怪的名字去这个词根表里找**最长的**命中
    （"黄金龙"里命中"龙" → 龙家族）。一个字的词根只在票数够时才认，避免乱并。
    """
    stem_votes = {}
    family_size = {}
    for row in rows:
        family = row.get("family") or ""
        if not family:
            continue
        family_size[family] = family_size.get(family, 0) + 1
        stem = name_stem(row["name"])
        if len(stem) < 1:
            continue
        votes = stem_votes.setdefault(stem, {})
        votes[family] = votes.get(family, 0) + 1

    for row in rows:
        override = FAMILY_OVERRIDES.get(row["name"])
        if override:
            row["family"] = override
            continue
        name = row["name"]
        # 名字里的物种词优先：id 被作者挪用的情况（剑神·沙士 的 id 是 goldSlime、
        # 皇室剑士 的 id 是 skeletonKnight）也靠这一条归到对的类型
        if row.get("family") != "boss":
            for word, family in SPECIES_WORDS:
                if word in name:
                    row["family"] = family
                    break
        if row.get("family"):
            continue
        best, best_len, best_votes = "", 0, 0
        for stem, votes in stem_votes.items():
            if not stem or stem not in name:
                continue
            for family, count in votes.items():
                if family == "boss":
                    continue
                if len(stem) <= 1 and family_size.get(family, 0) < 2:
                    continue                  # 一个字的词根要求那个家族够大
                better = (len(stem), count) > (best_len, best_votes)
                if better:
                    best, best_len, best_votes = family, len(stem), count
        row["family"] = best or ("x_" + name_stem(name))
    return rows


def sorted_rows(rows):
    """排序 + 编号。家族名次 = 家族里最早出现的那个怪在源文件里的位置。"""
    out = list(rows)
    family_rank = {}
    for row in out:
        family = row.get("family") or ""
        rank = row.get("source_rank") or 0
        if family not in family_rank or rank < family_rank[family]:
            family_rank[family] = rank
    for row in out:
        row["family_rank"] = family_rank.get(row.get("family") or "", 99999)
    out.sort(key=SORT_KEY)
    for position, row in enumerate(out, start=1):
        row["seq"] = position
    return out


SCHEMA = """
CREATE TABLE IF NOT EXISTS enemy (
    id       INTEGER PRIMARY KEY,   -- 稳定内部 id（按图片指纹保住，重跑不变）
    seq      INTEGER NOT NULL,      -- 编号：按强弱排序后的名次，界面显示 #001
    name     TEXT    NOT NULL,
    key      TEXT,                  -- enemys.js 里的 id
    tower    TEXT,                  -- 取自哪座塔
    towers   TEXT,                  -- 合并后涉及的塔（逗号分隔）
    hp       INTEGER, atk INTEGER, def INTEGER,
    money    INTEGER, exp INTEGER, agi INTEGER, cri INTEGER,
    power    INTEGER,               -- hp × atk（排序口径，见 SORT_KEY）
    icon     TEXT,                  -- 相对 assets 的缩略图路径，'' = 没图
    picture  TEXT    NOT NULL UNIQUE,  -- 图片指纹（去重键）
    aliases  TEXT,                  -- 被合并掉的其它名字（JSON 数组）
    skills   TEXT,                  -- 空格分隔的技能名（从 special 码翻译过来）
    family   TEXT,                  -- 家族（greenSlime/slimelord → slime），同类型的排一起
    source_rank INTEGER             -- 在源文件里的位置（两塔：xinxin 在前）
);
CREATE INDEX IF NOT EXISTS idx_enemy_seq ON enemy(seq);
CREATE INDEX IF NOT EXISTS idx_enemy_family ON enemy(family, source_rank);

CREATE TABLE IF NOT EXISTS skill (
    id       INTEGER PRIMARY KEY,
    name     TEXT    NOT NULL UNIQUE,
    codes    TEXT,                  -- 出现过的特殊码（不同塔可能不同，如 "4,5"）
    towers   TEXT,                  -- 哪几座塔有这个技能
    code_min INTEGER                -- 最小特殊码：下拉框就按这个从小到大排
);

CREATE TABLE IF NOT EXISTS enemy_skill (
    enemy_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    PRIMARY KEY (enemy_id, skill_id)
);
"""


def write_db(rows, skill_pairs, path):
    """写库；已有行的 id 按图片指纹续上，界面/测试引用过的编号不会乱跳。"""
    old_ids = {}
    old_skill_ids = {}
    if os.path.exists(path):
        try:
            conn = sqlite3.connect(path)
            for row in conn.execute("SELECT id, picture FROM enemy"):
                old_ids[row[1]] = row[0]
            try:
                for row in conn.execute("SELECT id, name FROM skill"):
                    old_skill_ids[row[1]] = row[0]
            except sqlite3.Error:
                pass
            conn.close()
        except Exception as exc:
            print("旧库读不了（就当新建）：%r" % (exc,))
    next_id = max(old_ids.values()) + 1 if old_ids else 1
    next_skill_id = max(old_skill_ids.values()) + 1 if old_skill_ids else 1

    # 技能目录：同一名字在不同塔里可能对应不同码，合并成一行，码用逗号连起来
    catalog = {}
    for code, name, tower in skill_pairs:
        entry = catalog.setdefault(name, {"codes": [], "towers": []})
        if code not in entry["codes"]:
            entry["codes"].append(code)
        if tower not in entry["towers"]:
            entry["towers"].append(tower)
    skill_ids = {}
    for name in sorted(catalog, key=lambda n: (min(catalog[n]["codes"]), n)):
        skill_ids[name] = old_skill_ids.get(name) or next_skill_id
        if name not in old_skill_ids:
            next_skill_id += 1

    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        for row in rows:
            picture = row["picture"]
            if picture in old_ids:
                row_id = old_ids[picture]
            else:
                row_id = next_id
                next_id += 1
            conn.execute(
                "INSERT INTO enemy (id, seq, name, key, tower, towers, hp, atk,"
                " def, money, exp, agi, cri, power, icon, picture, aliases,"
                " skills, family, source_rank)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row_id, row["seq"], row["name"], row["key"], row["tower"],
                 row["towers"], row["hp"], row["atk"], row["def"],
                 row["money"], row["exp"], row["agi"], row["cri"],
                 row["hp"] * row["atk"], row["icon"], picture,
                 row["aliases"], row["skills"], row.get("family", ""),
                 row.get("source_rank", 0)))
            for token in (row["skills"] or "").split():
                skill_id = skill_ids.get(token)
                if skill_id is None:
                    # 名册里没有的（理论上不该发生）：补进目录，别丢关系
                    skill_id = next_skill_id
                    next_skill_id += 1
                    skill_ids[token] = skill_id
                    catalog[token] = {"codes": [], "towers": []}
                conn.execute("INSERT OR IGNORE INTO enemy_skill"
                             " (enemy_id, skill_id) VALUES (?,?)",
                             (row_id, skill_id))
        for name, info in catalog.items():
            conn.execute(
                "INSERT INTO skill (id, name, codes, towers, code_min)"
                " VALUES (?,?,?,?,?)",
                (skill_ids[name], name,
                 ",".join(str(c) for c in sorted(info["codes"])),
                 ",".join(info["towers"]),
                 min(info["codes"]) if info["codes"] else 999))
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    towers = DEFAULT_TOWERS
    if len(sys.argv) > 2:
        towers = sys.argv[1:3]
    pairs = [(label, path) for label, path in zip(LABELS, towers)
             if os.path.isdir(path)]
    if not pairs:
        print("两座塔的目录都不在，退出")
        return 1

    mapping = load_icon_map()
    raw, skill_pairs = collect(pairs, mapping)
    merged_rows = assign_families(merge(raw))
    rows = [row for row in merged_rows if row.get("icon")]
    SKIPPED["no_icon"] = [row["name"] for row in merged_rows if not row.get("icon")]
    kept = []
    for row in rows:
        why = looks_placeholder(row)
        if why:
            SKIPPED["anomaly"].append("%s（%s）" % (row["name"], why))
            continue
        kept.append(row)
    rows = sorted_rows(kept)
    write_db(rows, skill_pairs, DB_PATH)

    print("原始条目 %d 条，按图片去重后 %d 条（%d 张有图 / %d 只没图）"
          % (len(raw), len(rows),
             len([r for r in rows if r["icon"]]),
             len([r for r in rows if not r["icon"]])))
    dup = len(raw) - len(rows)
    print("图片指纹聚成 %d 张（其中 %d 个文件被判成同一张图）"
          % (len(_PICTURE_REPS), _PICTURE_STATS["merged"]))
    print("合并掉的重复图片 %d 条，编号 #%03d ~ #%03d"
          % (dup, rows[0]["seq"], rows[-1]["seq"]))
    families = []
    for row in rows:
        if row["family"] not in families:
            families.append(row["family"])
    print("家族 %d 个，顺序：%s%s"
          % (len(families), " → ".join(families[:12]),
             " → …" if len(families) > 12 else ""))
    print("前 6 只：" + "、".join(
        "#%03d %s(%s)" % (r["seq"], r["name"], r["family"]) for r in rows[:6]))
    skills = sorted({tok for r in rows for tok in (r["skills"] or "").split()})
    with_skill = [r for r in rows if (r["skills"] or "").strip()]
    print("清理：数值全空 %d 只、没有立绘 %d 只、数值异常 %d 只，都没进库"
          % (len(SKIPPED["no_stats"]), len(SKIPPED["no_icon"]),
             len(SKIPPED["anomaly"])))
    if SKIPPED["anomaly"]:
        print("  数值异常：" + "；".join(SKIPPED["anomaly"]))
    if SKIPPED["no_stats"]:
        print("  数值全空：" + "、".join(SKIPPED["no_stats"][:20]))
    if SKIPPED["no_icon"]:
        print("  没有立绘：" + "、".join(SKIPPED["no_icon"][:20]))
    print("技能目录 %d 条（两座塔的 specials 表合并），%d/%d 只怪带技能"
          % (len({name for _, name, _ in skill_pairs}), len(with_skill), len(rows)))
    print("技能举例：" + "、".join(skills[:12]))
    print("写入 %s" % DB_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
