"""素材库访问：读 assets/library/manifest.json，给界面和读取逻辑提供图标。

素材库现在只有一种东西：**两座新新魔塔里的怪物图 + 名字**
（用户："下载里有两个新新魔塔的游戏，把那里面的怪物和名字加入素材库，
把之前的素材都删掉"）。图只在 `assets/library/monster/` 一处，文件名＝
编号 + 种族 + 英文名（规则见 `chaita/library_names.py`），由 `tools/build_library.py`
一条流水线切出来并写进 manifest。名字取那座塔 enemys.js 里的 name。
分类只剩 `monster`；`item/weapon/door/...` 这些旧分类已经删了。

顺序也是这里定的（用户："素材库怪物的ID需要更新：1.同类的要相连
2.弱的排前面（不同类按每一类里最弱的排）"）：`arrange()` 给每只怪算
`kind`（同类）+ `power`（强弱）+ `order`（显示序号），manifest 按这个顺序写，
`items()` 再按 `order` 排一次 —— 老的 manifest 没有这些字段也不会乱。
"""

import json
import os
import re

from . import library_names
from .paths import ROOT
LIBRARY_DIR = os.path.join(ROOT, "assets", "library")
MANIFEST = os.path.join(LIBRARY_DIR, "manifest.json")

_CACHE = {}

# 动画帧的后缀：`monster/120_0`、`monster/120_1` 是同一只怪的两帧
_FRAME_SUFFIX = re.compile(r"_\d+$")

# ---- 显示顺序：同类相连、弱的在前 ----
# 「同类」怎么认：塔里的怪 id 是英文（greenSlime / skeletonPriest），
# 数字 id（E330…）只有中文名字。所以两边都看：**先认生物科，再认职业** ——
#   · `skeletonPriest`（骷髅法师）、`skeletonKing`（骷髅王）→ 骷髅，不是法师/魔王；
#   · `soldier` 这一格的图其实是「灵骷髅兵」→ 名字里的"骷髅"先把它归进骷髅。
# 认不出的怪自己成一堆（其他），排在最后。
CREATURE_KINDS = [
    # 人形史莱姆单独一个种族（用户："史莱姆人单独一个种族"），
    # 必须排在"史莱姆"前面，不然名字里的"史莱姆"先把它抢走
    ("史莱姆人", ("史莱姆人",), ("slimeMan",)),
    ("史莱姆", ("史莱姆",), ("slime",)),
    # 死灵单独一个种族（用户："死灵是一个种族，冻死骨是骷髅"）——
    # 排在骷髅前面，所以"死灵大法师/死灵术士/死灵战士"归死灵；
    # 「冻死骨」名字里只有"骨"，还是留在骷髅那边
    ("死灵", ("死灵",), ()),
    ("骷髅", ("骷髅", "骨"), ("skeleton",)),
    ("蝙蝠", ("蝙蝠", "蝠"), ("bat",)),
    ("丧尸", ("丧尸", "僵尸"), ("zombie",)),
    ("幽灵", ("幽灵", "水银"), ("ghost",)),
    ("八爪鱼", ("八爪鱼", "章鱼"), ("octopus",)),
    ("石怪", ("石",), ("rock",)),
    ("矮人", ("矮人",), ()),
    ("龙", ("龙",), ("dragon",)),
    ("植物", ("植物", "触手"), ()),
    ("马", ("马",), ()),
    ("眼", ("魔眼", "邪眼"), ()),
    ("仙子", ("妖精", "仙子"), ("fairy",)),
    ("公主", ("公主", "魔女"), ("princess",)),
    ("勇者", ("勇者", "自己"), ("hero",)),
    ("天使", ("天使",), ("angel",)),
    ("元素", ("元素",), ("elemental",)),
    ("灵", ("生气灵",), ()),
]

ROLE_KINDS = [
    # 用户："090，092归为魔神" —— 魔神单独一族（名字里带"魔神"的只有这两只，
    # 用 RACE_BY_KEY 精确定位，别把"魔神·些多"也抢过来）
    ("魔神", (), ()),
    # 用户："沿用 swordsman" —— 剑士单独一族；中文名/英文名都不带匹配词，
    # 靠下面的 RACE_BY_KEY 精确指定（名字里带"剑士"的别被它抢走）
    ("剑士", (), ()),
    # 用户："种族改成长袍魔法师，蓝的初级，黄的中级，红的高级，黑的混沌"
    # —— 一套兜帽长袍换了四种颜色，统一成一个种族，名字按颜色分级别
    ("长袍魔法师", ("长袍魔法师",), ()),
    ("骑士", ("骑士", "剑士", "剑圣", "剑王", "剑", "盾", "枪兵", "战士"),
              ("knight", "swordsman", "swordemperor", "soldier")),
    ("守卫", ("守卫",), ("guard",)),
    # 「箭神·法比」是弓兵那边的 boss，不能因为名字里有个"神"就算魔王
    ("弓兵", ("弓兵", "箭"), ("archer",)),
    # 用户："术士是一个种族，法师是一个种族，魔法师是一个种族" ——
    # 三套不同的图，得分开；顺序也有讲究（「魔法师」先于「法师」，
    # 不然后者会把「魔法师首领」也吃掉）
    ("魔法师", ("魔法师",), ()),
    ("术士", ("术士",), ()),
    ("法师", ("法师",), ("wizard", "magician", "priest")),
    ("魔王", ("魔王", "王", "神", "凯撒", "柏奇"), ("king", "vamp", "demon")),
]

# ---- 名字看不出来的：贴图键 → 种族（**看图标定的**） ----
# 用户："有三个魔王是属于魔法师的，有一个斗神是属于守卫的" —— 这三只"魔王"
# 和魔法师首领/元帅是同一套铠甲图，"斗神·高巴"和守卫是同一套。名字里看不出来，
# 按图认。用户："总之你没有看图来分类"。
# `(塔, 贴图键)` → 种族：同一个贴图键在两座塔里可能是不同的怪，所以按塔区分
RACE_BY_KEY = {
    ("xinxin", "swordsman"): "剑士",        # 双手剑兵：褐色壮汉、空手，不是骑士
    # 用户："058 / 059 删有背景的，是剑士" —— 两只剑王都归剑士族
    ("xinxin2", "redSwordsman"): "剑士",
    ("xinxin", "redSwordsman"): "剑士",
    # 用户："69和106是一个族的都是死灵前缀" —— 暗黑魔法师、灵武士都归死灵
    ("xinxin", "demonPriest"): "魔神",      # 魔神法师
    ("xinxin2", "demon"): "魔神",           # 魔神武士
    ("xinxin", "blackMagician"): "死灵",
    ("xinxin", "darkKnight"): "死灵",
    ("xinxin2", "blackMagician"): "死灵",
    ("xinxin2", "darkKnight"): "死灵",
}

RACE_BY_EID = {
    "blackKing": "魔法师",    # 黑衣魔王：和魔法师首领/元帅同一套铠甲图
    "yellowKing": "魔法师",   # 魔王
    "redKing": "魔法师",      # 大魔王
    "E380": "守卫",           # 斗神·高巴：和守卫（黄卫兵）同一套图
}

KINDS = CREATURE_KINDS + ROLE_KINDS
KIND_NAMES = [name for name, _, _ in KINDS]
UNKNOWN_KIND = "其他"

# 用户点名要挪顺序的（"放在024前"、"019后放027和021"、"21后是25 23"）：
# 种族 → [(要挪的那几只, 锚点名字, "before"/"after"), ...]，按顺序一条条执行。
# 要挪的每只写成 `名字` 或 `(名字, 贴图键)` —— 同名两只（骷髅兵）靠贴图键分清是哪个。
KIND_PLACE = {
    # 用户："77移到76之前" —— 仙子 排到 黑暗妖精 前面
    "仙子": [
        (("仙子",), "黑暗妖精", "before"),
    ],
    # 用户："72移动到71之前" —— 魔王·格勒第 排到 魔神·些多 前面
    "魔王": [
        (("魔王·格勒第",), "魔神·些多", "before"),
    ],
    # 用户："黄的在红的前"
    "长袍魔法师": [
        (("黄色长袍魔法师",), "红色长袍魔法师", "before"),
    ],
    "骷髅": [
        (("灵骷髅", "灵骷髅兵"), "重生骷髅兵", "before"),
        (("高级骷髅兵", "骷髅武士"), "中级骷髅兵", "after"),
        (("灵骷髅", ("骷髅兵", "E329")), "骷髅武士", "after"),
        (("灵骷髅兵", "骷髅战士"), ("骷髅兵", "E329"), "after"),
        # 用户："027放到023后"（上一句 "017" 是他打错了：017 骷髅不动）
        (("重生骷髅兵",), ("骷髅兵", "E329"), "after"),
    ],
}

# 建库时按图上主色算出的 `colour` → 档位（蓝=1 绿=2 黄=3 红=4 黑/紫=5 灰白=6）
COLOUR_TIER = {"blue": 1, "green": 2, "yellow": 3, "red": 4,
               "black": 5, "purple": 5, "grey": 6, "white": 6}


# 某个种族要排到另一个种族后面（用户："剑士放在骑士后"）
KIND_AFTER = {
    "长袍魔法师": "蝙蝠",   # 用户："长袍魔法师在蝙蝠后"
    "剑士": "骑士",
    "弓兵": "剑士",     # 用户："弓兵移到剑士后"
    "石怪": "守卫",     # 用户："石怪在守卫后"
    "仙子": "公主",     # 用户："仙子放公主后"
}

# 某个种族要排到另一个种族**前面**（用户："勇者放公主前"）
KIND_BEFORE = {
    "勇者": "公主",
}

# 还没定归属的（用户："我不知道，待定，移到最后"）：排到最后，别混进任何一族
PENDING_NAMES = ()     # 三条都定了：铁守卫删掉，魔神法师/魔神武士归"魔神"

# 强弱分数：hp 是"要打几回合"，atk/def 是"每回合的代价"，后者按 10 倍折算
# （魔塔里攻防比血量值钱得多，防御高到 9999 的那几只本来就是打不动的）
POWER_ATK = 10
POWER_DEF = 10


def _hit(text: str, words) -> bool:
    return any(word and word in text for word in words)


def kind_of(eid, name: str = "") -> str:
    """这只怪归哪一类；认不出返回空串（排到最后的「其他」里）。

    **先看看图标定的表**（`RACE_BY_EID`：名字看不出来的那几只按贴图归），
    **再看名字，最后看贴图 id**：玩家看到的是名字，而 id 只是那张贴图在塔里的键 ——
    同一张贴图在两座塔里可能挂给完全不同的怪（`xinxin2` 的 `goldSlime` 是
    「剑神·沙士」，一只金甲骑士），先看 id 会把它塞进史莱姆堆里
    （用户："有明明是同类但没放在一起的"）。
    """
    fixed = RACE_BY_EID.get(str(eid or ""), "")
    if fixed:
        return fixed
    name_text = str(name or "")
    for pool in (CREATURE_KINDS, ROLE_KINDS):
        for kind, chinese, _english in pool:
            if _hit(name_text, chinese):
                return kind
    id_text = str(eid or "").lower()
    for pool in (CREATURE_KINDS, ROLE_KINDS):
        for kind, _chinese, english in pool:
            if _hit(id_text, english):
                return kind
    return ""


def power_of(hp, atk, def_) -> object:
    """强弱分数 `hp + 10*(atk+def)`；hp/atk/def 全 0（塔里没填、占位怪）返回 None。"""
    try:
        hp, atk, def_ = int(hp), int(atk), int(def_)
    except (TypeError, ValueError):
        return None
    if hp == 0 and atk == 0 and def_ == 0:
        return None
    return hp + POWER_ATK * atk + POWER_DEF * def_


# 占位/废弃/不要的名字：不摆进选图界面
# （"新敌人"是模板占位；"史莱姆阿修罗"用户点名："史莱姆阿修罗删掉"）
# 用户点名不要的（"把这三个都删掉吧"）：建库时直接不收，盘上也不生成文件
HIDDEN_NAMES = ("新敌人", "史莱姆阿修罗", "水银人",
                "魔剑之凯撒", "灵盾之柏奇", "血剑士",
                "魔界之王·古顿",          # 用户："73删掉"
                "恶魔首领",               # 用户："74删掉"（纯色空图，不是素材）
                "天使", "元素生物",        # 用户："天使 元素生物 都删掉"
                "生气灵",                 # 用户："灵 这个也删掉"
                "冥界矮人战士",            # 用户："矮人也删掉"
                "魔眼",                   # 用户："眼 也删掉"
                "地狱马",                 # 用户："马 也删掉"
                "血使者",                 # 用户："090 也删掉"
                "铁守卫")                 # 用户："091删掉"
# 名字里带这几个字的也不要（"毒龙（已弃用）"）
HIDDEN_WORDS = ("已弃用",)


def _hidden(entry) -> bool:
    name = str(entry.get("name") or "")
    return name in HIDDEN_NAMES or any(word in name for word in HIDDEN_WORDS)


def _common_suffix(a: str, b: str) -> str:
    """公共后缀（中文的"头"在最后：史莱姆**王**、史莱姆**人**）。"""
    size = 0
    while (size < len(a) and size < len(b)
           and a[-1 - size] == b[-1 - size]):
        size += 1
    return a[len(a) - size:] if size else ""


def _common_prefix(a: str, b: str) -> str:
    size = 0
    while size < len(a) and size < len(b) and a[size] == b[size]:
        size += 1
    return a[:size]


def _family_key(a: str, b: str):
    """两个名字共同的"型号"：`(优先级, 共有的那段字)`。

    用户："史莱姆放一起，史莱姆人放一起"：
      · 后缀优先（中文的"头"在最后）：史莱姆王 / 白银史莱姆王 → 「史莱姆王」；
        史莱姆人 / 四手史莱姆人 → 「史莱姆人」；白银史莱姆 / 绿色史莱姆 → 「史莱姆」
      · 后缀不成才看前缀：魔法师首领 / 魔法师元帅 → 「魔法师」
    """
    suffix = _common_suffix(a, b)
    if len(suffix) >= 2:
        return (0, suffix)
    prefix = _common_prefix(a, b)
    if len(prefix) >= 2:
        return (1, prefix)
    return None


def _family_of(names) -> dict:
    """同一类里按"型号"分家：`{名字: 家族标签}`。

    先把所有"后缀相同"的对子连起来（这些才是同一个型号），再拿前缀补剩下的；
    这样「白银史莱姆王」会跟着「史莱姆王」，而不是被「白银史莱姆」这个颜色前缀拽走。
    """
    label = {}
    words = list(names)
    pairs = []
    for index, first in enumerate(words):
        for second in words[index + 1:]:
            key = _family_key(first, second)
            if key:
                pairs.append((key[0], -len(key[1]), key[1], first, second))
    pairs.sort()
    for _order, _length, shared, first, second in pairs:
        first_label = label.get(first)
        second_label = label.get(second)
        if first_label is None and second_label is None:
            label[first] = label[second] = shared
        elif first_label == shared and second_label is None:
            label[second] = shared
        elif second_label == shared and first_label is None:
            label[first] = shared
    for name in words:
        label.setdefault(name, name)
    # 标签收口：`色史莱姆` 只是「史莱姆」前面多了一截颜色，算同一家；
    # `大法师` 归到「法师」。判断只看后缀（史莱姆王 末尾是 王，不会被并进史莱姆）
    tags = sorted(set(label.values()), key=len)
    for index, tag in enumerate(tags):
        for other in tags[:index]:
            if other != tag and tag.endswith(other):
                for name, value in label.items():
                    if value == tag:
                        label[name] = other
                break
    return label


# ---- 一眼看上去是一类的（**看图标定的**，不是按名字猜的） ----
# 用户："你还要看图，究竟哪几个哪几个像"。这里是人工分好的"型号"表：
# 同一组里的是长得像的（史莱姆圆滚滚的一堆、史莱姆人形的一堆、戴王冠的一堆…）。
# 表里没列到的名字，退回前面那套按名字分家的规则。
VISUAL_GROUPS = [
    # 史莱姆：圆的（颜色不同还是一只）
    ["白银史莱姆", "黄金史莱姆", "绿色史莱姆", "红色史莱姆", "黑色史莱姆",
     "邪眼史莱姆"],
    # 人形史莱姆（两条腿的）
    ["史莱姆人", "四手史莱姆人"],
    # 戴王冠的史莱姆
    ["史莱姆王", "白银史莱姆王", "黄金史莱姆王"],
    # 长角的史莱姆
    ["尖角怪", "金角怪"],
    # 蝙蝠
    ["蝙蝠", "大蝙蝠", "邪恶蝙蝠", "红蝙蝠", "毒蝙蝠", "龙蝠"],
    # 骷髅（拿刀枪的）
    ["骷髅", "骷髅兵", "中级骷髅兵", "重生骷髅兵", "不死骷髅兵",
     "骷髅战士", "骷髅队长", "骷髅头目", "骷髅武士", "骷髅王"],
    # 骷髅里的法师/巫师
    ["骷髅法师", "骷髅巫师"],
    # 黑袍/黑甲的死灵（看着是同一套图）
    ["死灵大法师", "死灵术士", "死灵战士"],
    ["冻死骨"],
    # 丧尸
    ["丧尸", "丧尸剑士", "烈焰丧尸", "毒丧尸"],
    # 守卫
    ["守卫", "中级守卫", "高级守卫", "铁守卫"],
    # 骑士（同一套铠甲图换色：骑士 / 铁骑士 / 近卫骑士 / 强盾骑士）
    ["骑士", "铁骑士", "近卫骑士", "强盾骑士"],
    # 剑士（拿剑的士兵：双手剑士 / 血剑士 / 皇室剑士 / 皇室枪兵 / 不死战士）
    ["双手剑士", "血剑士", "皇室剑士", "皇室枪兵", "不死战士"],
    # 剑王那一挂的 boss（剑王 / 剑神·沙士 / 魔剑之凯撒 / 灵盾之柏奇 / 剑圣）
    ["剑王", "剑圣", "剑神·沙士", "魔剑之凯撒", "灵盾之柏奇"],
    # 法师：兜帽法袍的三只（魔术师 / 雷术士 / 炎术士 是同一套图换色）
    ["魔术师", "雷术士", "炎术士"],
    # 王袍的两只（魔法师首领 / 魔法师元帅 同一套图）
    ["魔法师首领", "魔法师元帅"],
    # 尖帽法师（大法师 / 红衣大法师 / 火炎大法师 / 极地法师 同一套图换色）
    ["大法师", "红衣大法师", "火炎大法师", "极地法师"],
    # 重甲法师（暗黑魔法师 / 魔神法师）
    ["暗黑魔法师", "魔神法师"],
    ["混沌术士"],
    # 石怪
    ["石怪", "石头怪", "铁怪", "鬼邪石"],
    # 八爪鱼
    ["八爪鱼", "毒八爪鱼", "魔界八爪鱼", "闪光八爪鱼"],
    # 弓兵
    ["弓兵", "精锐弓兵", "箭神·法比"],
    ["假公主", "痛苦魔女"],
    ["自己", "迷失勇者"],
    # 魔王（穿黑袍/金甲的）
    ["黑衣魔王", "黑魔王", "魔王", "魔王近卫兵", "大魔王", "魔王·格勒第"],
    # 魔神/斗神/魔界之王（黄翅膀、暗甲那一挂）
    ["魔神·些多", "斗神·高巴", "魔神武士", "魔界之王·古顿", "恶魔首领"],
    # 龙
    ["恶龙", "毒龙", "黄金龙"],
    ["魔眼"],
    ["水银人"],
    ["触手植物", "触手魔物"],
    ["生气灵"],
    ["冥界矮人战士"],
    ["地狱马"],
    ["黑暗妖精", "仙子"],
    ["天使"],
    ["元素生物"],
    ["血使者"],
]

_VISUAL_INDEX = {}
for _group_index, _group in enumerate(VISUAL_GROUPS):
    for _name in _group:
        _VISUAL_INDEX.setdefault(_name, "看:%d" % _group_index)


def family_of(name: str, kind: str = "") -> str:
    """这个名字的"型号"：先查看图定的表，没列到的退回按名字分家。"""
    name = str(name or "")
    if name in _VISUAL_INDEX:
        return _VISUAL_INDEX[name]
    return "名:" + name


# ---- 塔里的先后：这就是游戏自己的"弱到强" ----
# 两座塔 `project/enemys.js` 里怪物的排列顺序（史莱姆 → 蝙蝠 → 骷髅 → 丧尸 →
# 石怪 → 法师 → 守卫 → 骑士 → 魔王 → 龙 …），作者本来就是按关卡/强弱排的。
# 用户："不同种类的顺序说了按同类里最弱的排你排了吗？蝙蝠怎么这么靠后" ——
# 用塔里的先后当"强弱"，比自己编的 hp+10*(攻+防) 靠谱，也正好把蝙蝠排在史莱姆后面。
# 表由 `tools/dump_tower_order.py` 从 enemys.js 抄下来（两座塔：新新魔塔 + 新新魔塔2）。
TOWER_ORDER = [
    "greenSlime", "redSlime", "blackSlime", "slimelord", "bat", "bigBat",
    "redBat", "vampire", "skeleton", "skeletonSoilder", "skeletonCaptain",
    "ghostSkeleton", "zombie", "zombieKnight", "rock", "slimeMan",
    "bluePriest", "redPriest", "brownWizard", "redWizard", "yellowGuard",
    "blueGuard", "redGuard", "swordsman", "soldier", "yellowKnight",
    "redKnight", "darkKnight", "blackKing", "yellowKing", "greenKing",
    "blueKnight", "goldSlime", "poisonSkeleton", "poisonBat", "steelRock",
    "skeletonPriest", "skeletonKing", "skeletonWizard", "redSkeletonCaption",
    "badHero", "demon", "demonPriest", "goldHornSlime", "redKing",
    "whiteKing", "blackMagician", "silverSlime", "swordEmperor",
    "whiteHornSlime", "badPrincess", "badFairy", "grayPriest",
    "redSwordsman", "whiteGhost", "poisonZombie", "magicDragon", "octopus",
    "darkFairy", "greenKnight", "angel", "elemental", "steelGuard",
    "evilBat", "E300", "E301", "E302", "E303", "E304", "E305", "E306",
    "E307", "E329", "E330", "E331", "E332", "E333", "E334", "E335", "E336",
    "E337", "E377", "E378", "E379", "E380", "E381", "E382", "E383", "E384",
    "E385", "E396", "E397", "E411", "E413", "E414", "E431", "E432", "E433",
    "E434", "E435", "E436", "E437", "E438", "E439", "E440", "E441", "E442",
    "E443", "E444", "E446", "E447", "vamp",
]
_POS = {eid: index for index, eid in enumerate(TOWER_ORDER)}
UNKNOWN_POS = 10 ** 6


def position_of(entry) -> int:
    """这只怪在塔里的第几个（不在表里的排最后）。"""
    return _POS.get(str((entry or {}).get("eid") or ""), UNKNOWN_POS)


def _normalized(rows) -> list:
    """给每项算好 `kind` / `power` / `pos`（返回新 dict，不动传进来的）。

    分类总是按当前规则重算：整类规则改了（名字优先）以后，
    manifest 里存着的旧 kind 不能再用（见 `load()`）。
    """
    items = []
    for row in rows:
        item = dict(row)
        item["kind"] = (RACE_BY_KEY.get(
            (str(item.get("tower") or ""), str(item.get("eid") or "")))
            or kind_of(item.get("eid"), item.get("name"))
            or UNKNOWN_KIND)
        item["power"] = power_of(item.get("hp"), item.get("atk"),
                                 item.get("def"))
        item["pos"] = position_of(item)
        items.append(item)
    return items


def _fold_singletons(items) -> list:
    """只有一个的类并进「其他」（用户："所有只有一个的种族全部归为其他"）。

    数的是**摆出来的**那一批（隐藏的、并掉的都收掉之后，见 `pictures()`）：
    「自己 / 迷失勇者」是一对重复图，按原始条目数会把「勇者」凑成两只，
    界面上却只看得见一只 —— 规则说的是看到的列表。
    """
    counts = {}
    for item in items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    for item in items:
        if counts.get(item["kind"]) == 1 and item["kind"] != UNKNOWN_KIND:
            item["kind"] = UNKNOWN_KIND
    return items


def _sorted_by_kind(items) -> list:
    """同类相连：类按类里最早出现的那只排，类里按型号，型号里按塔里的先后。

    「其他」不是真类，是兜底筐，永远排最后（`group_key` 里没名的类靠后）。
    """
    groups = {}
    for item in items:
        groups.setdefault(item["kind"], []).append(item)

    def group_key(pair):
        kind, group = pair
        # 用户："按每个种族最弱的怪给所有种族排序" —— 族与族之间按**该族最弱的 power** 排；
        # 一只都算不出 power 的族排最后
        powers = [one["power"] for one in group if one["power"] is not None]
        weakest = min(powers) if powers else None
        return (weakest is None, weakest or 0, str(kind))

    ordered = []
    for _kind, group in sorted(groups.items(), key=group_key):
        # 类里：先按型号（同一套图换色的挨着），型号之间按塔里最早出现的那只，
        # 型号内部按塔里的先后，再按强弱/名字兜底（重跑顺序稳定）
        names = [str(one.get("name") or "") for one in group]
        by_name = _family_of(names)
        family = {name: family_of(name) for name in names}
        for name in names:
            if family[name].startswith("名:"):
                # 看图表里没有的：用它按名字分到的那一家
                family[name] = "名:" + by_name.get(name, name)
        first = {}
        for one in group:
            key = family.get(str(one.get("name") or ""), "")
            first[key] = min(first.get(key, one["pos"]), one["pos"])
        for one in group:
            one["family"] = family.get(str(one.get("name") or ""), "")
        # 用户："先做强弱排序" —— 族内按 power（hp + 10*(atk+def)）从弱到强；
        # power 相同再按型号聚一聚、然后按塔里的先后（保证顺序稳定）
        group.sort(key=lambda one: (
            # 先按魔塔的颜色档位（蓝<绿<黄<红<黑，按图上主色），再按 power（弱→强）
            COLOUR_TIER.get(str(one.get("colour") or ""), 99),
            one["power"] is None,
            one["power"] or 0,
            first.get(family.get(str(one.get("name") or ""), ""), UNKNOWN_POS),
            one["pos"],
            str(one.get("name") or ""),
            str(one.get("tower") or "")))
        for movers, anchor, mode in KIND_PLACE.get(_kind) or ():
            def matches(one, spec):
                """`名字` 或 `(名字, 贴图键)`。"""
                if isinstance(spec, tuple):
                    return (str(one.get("name") or "") == spec[0]
                            and str(one.get("eid") or "") == spec[1])
                return str(one.get("name") or "") == spec

            picking = [one for spec in movers for one in group
                       if matches(one, spec)]
            if not picking:
                continue
            keep = []
            for one in group:
                if any(one is chose for chose in picking):
                    continue
                keep.append(one)
            spot = next((index for index, one in enumerate(keep)
                         if matches(one, anchor)),
                        len(keep))
            if mode == "after":
                spot += 1
            keep[spot:spot] = picking
            group = keep
        ordered.extend(group)
    # 某个种族整块挪到另一个种族后面（"剑士放在骑士后"）
    for mover, host in KIND_AFTER.items():
        block = [one for one in ordered if one.get("kind") == mover]
        if not block:
            continue
        rest = [one for one in ordered if one.get("kind") != mover]
        last_host = None
        for index, one in enumerate(rest):
            if one.get("kind") == host:
                last_host = index
        if last_host is None:
            continue
        rest[last_host + 1:last_host + 1] = block
        ordered = rest

    # 某个种族整块挪到另一个种族前面（"勇者放公主前"）
    for mover, host in KIND_BEFORE.items():
        block = [one for one in ordered if one.get("kind") == mover]
        if not block:
            continue
        rest = [one for one in ordered if one.get("kind") != mover]
        first_host = next((index for index, one in enumerate(rest)
                           if one.get("kind") == host), None)
        if first_host is None:
            continue
        rest[first_host:first_host] = block
        ordered = rest

    # 待定的排到最后（顺序保持稳定）
    if PENDING_NAMES:
        tail = [one for one in ordered
                if str(one.get("name") or "") in PENDING_NAMES]
        if tail:
            ordered = [one for one in ordered
                       if str(one.get("name") or "") not in PENDING_NAMES]
            ordered.extend(tail)
    for index, item in enumerate(ordered):
        item["order"] = index
    return ordered


def arrange(rows) -> list:
    """算好 kind/power，并定出显示顺序（每项的 `order`，0 起）。

    **manifest 里已经有 `order` 的就照它的来** —— 那是 owner 一张张核过、后来
    又亲手挪过的顺序（`docs/WORKFLOW_MONSTER_NAMING.md` 第 6 节那张表）。
    以前这里无条件按"同类相连 → 类里按颜色档位/power"重排，等于每次读都把
    owner 定的顺序冲掉（用户："现在记住这个顺序"、"把其他该改的地方都改掉"）。

    只有**完全没有 order**（新切出来的、老 manifest）时才用规则排。
    """
    prepared = _normalized(rows)
    if prepared and all(isinstance(one.get("order"), int) for one in prepared):
        prepared.sort(key=lambda one: one["order"])
        return prepared
    return _sorted_by_kind(prepared)


def load() -> dict:
    """读 manifest（按修改时间缓存）。

    读进来**按当前规则重排一次**（`arrange()`）：分类/顺序的规则写在代码里，
    manifest 只是缓存；规则改了不用重新生成素材（生成要本机的两座塔）。
    """
    try:
        stamp = os.path.getmtime(MANIFEST)
    except OSError:
        return {"count": 0, "items": []}
    if _CACHE.get("stamp") == stamp:
        return _CACHE.get("data") or {"count": 0, "items": []}
    try:
        with open(MANIFEST, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        data = {"count": 0, "items": []}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        data = {"count": 0, "items": []}
    else:
        entries = [one for one in data["items"] if isinstance(one, dict)]
        ordered = arrange(entries)
        data = {"count": len(ordered), "items": ordered}
    _CACHE["stamp"] = stamp
    _CACHE["data"] = data
    return data


def _order_key(entry):
    """manifest 里的 order 就是显示顺序；老 manifest 没有就按原来的先后。"""
    order = entry.get("order")
    if isinstance(order, int):
        return (0, order, "")
    return (1, 0, str(entry.get("id") or ""))


def items(category: str = None) -> list:
    entries = load().get("items") or []
    if category:
        entries = [entry for entry in entries
                   if entry.get("category") == category]
    return sorted(entries, key=_order_key)


def display_name(entry) -> str:
    """素材的显示名：manifest 里有真名字就用它（塔里的怪就是怪物名），没有就用编号。"""
    if not isinstance(entry, dict):
        return ""
    name = str(entry.get("name") or "").strip()
    if name:
        return name
    return str(entry.get("id") or "").split("/")[-1]


# 文件名里进不了的字符、怎么拼，全在 `chaita/library_names.py`（种族 + 英文名）


def file_stem(entry) -> str:
    """素材文件叫什么 —— **编号 + 种族 + 名字，全 ASCII**（`073_guard_e380`）。

    用户："种族加名字，并且禁止使用中文"、"禁止使用拼音"、"给素材名字里加ID
    确保弱的在前面"：名字那一截走 `chaita/library_names.py` 里的英文表，
    编号是 `order`（显示序号，最弱的在前）。以前照抄贴图键
    （`xinxin2_E380.png`），在图库/资源管理器里根本看不出是哪只怪。

    文件名的唯一用途是给人看和排错：`id` 才是稳定键
    （`monster/<塔>_<贴图键>`，存盘、`icon_id` 都靠它），所以改名不动 id。
    """
    if not isinstance(entry, dict):
        return "icon"
    # 分类**当场重算**，不信 manifest 里存的那份：manifest 只是缓存，类规则改过以后
    # 旧 kind 会跟现在对不上（`剑神·沙士` 的老 kind 是「史莱姆」，照抄会把文件名叫成
    # `slime_sword_god_sash`）
    kind = (RACE_BY_KEY.get((str(entry.get("tower") or ""),
                             str(entry.get("eid") or "")))
            or kind_of(entry.get("eid"), entry.get("name"))
            or str(entry.get("kind") or "") or UNKNOWN_KIND)
    # 编号 = 显示序号（`order`）：用户："给素材名字里加ID确保弱的在前面"
    index = entry.get("order")
    return library_names.file_stem(
        kind, entry.get("name"), eid=entry.get("eid"), order=index,
        fallback="%s_%s" % (entry.get("tower") or "", entry.get("eid") or "icon"))


# 文件名最前面的显示序号（`092_guard_e380` 的 `092`）：重排顺序会变，认旧名字要能剥掉
_ORDER_PREFIX = re.compile(r"^\d{3,}_")


def id_of_file(stem: str) -> str:
    """文件名（不带扩展名）→ 素材 id：**老记录靠它找回图**。

    认这些写法：塔里的贴图键（`xinxin2_E380`）、中间那版中文名（`斗神·高巴`）、
    带编号的现在这个名字（`092_guard_e380`）、以及去掉编号的同一份
    （`guard_e380` —— 编号是显示序号，重排一次就会变，不能让存档跟着失效）。
    """
    stem = str(stem or "").strip()
    if not stem:
        return ""
    index = _index()
    direct = "monster/" + stem
    if direct in index:
        return direct
    plain = _ORDER_PREFIX.sub("", stem)
    for entry_id, entry in index.items():
        own = file_stem(entry)
        if own == stem or _ORDER_PREFIX.sub("", own) == plain:
            return entry_id
        if str(entry.get("name") or "") == stem:
            return entry_id
    return ""


def _index() -> dict:
    """id → 条目（每次 load 之后重建一次；按 id 取图不用把 600 条都扫一遍）。

    `alias_ids` 里记的是"同一只怪、另一座塔那份被并掉的 id"：存盘里的 `icon_id`
    可能是那一条，所以它也得指到留下来的这张图上。
    """
    data = load()                     # 先 load：它才会给 _CACHE 填 stamp
    stamp = _CACHE.get("stamp")
    if _CACHE.get("index_stamp") != stamp or not _CACHE.get("index"):
        index = {}
        for entry in data.get("items") or []:
            entry_id = entry.get("id")
            if entry_id:
                index[entry_id] = entry
            for alias in entry.get("alias_ids") or []:
                if alias:
                    index.setdefault(alias, entry)
        _CACHE["index"] = index
        _CACHE["index_stamp"] = stamp
    return _CACHE.get("index") or {}


def pictures(category: str = None) -> list:
    """**去重后**的素材（选图界面用）。

    重复在**建库的时候**就收掉了（`tools/build_library.py`：像素完全一样、
    名字一样、以及我一张张看图定的 `library_names.ART_MERGES`；并掉的 id 记在
    `alias_ids` 里，存档照样能查到图）。这里只剩两件事：
    1. 动画帧：同一只怪有 `120_0`、`120_1` 两帧，只留第一张；
    2. 占位/废弃的（`新敌人`、`（已弃用）`）不摆。

    收完再按**摆出来的张数**并掉"只有一个的类"（`_fold_singletons()`），
    然后重新排一次序：折进「其他」的那只得跟着「其他」的块走，不能留在老位置。
    """
    seen = set()
    out = []
    for entry in items(category):
        if _hidden(entry):
            continue
        base = _FRAME_SUFFIX.sub("", str(entry.get("id") or ""))
        key = (entry.get("category") or "", base)
        if key in seen:
            continue
        seen.add(key)
        row = dict(entry)
        # 同一张图在两座塔里叫不同名字的（`names` 里全记着）：全塞进别名，
        # 搜索照样搜得到，但只摆一张
        aliases = list(row.get("aliases") or [])
        for other in row.get("names") or []:
            if other and other != display_name(row) and other not in aliases:
                aliases.append(other)
        row["aliases"] = aliases
        out.append(row)
    # 用户："现在界面和文件顺序保持一致" —— 这里**不再把单只的族并进「其他」**，
    # 顺序也**直接按 manifest 的 order（= 文件名编号）**，不重排：
    # 那个 order 是 owner 一张张看过、又亲手挪过的（见 naming 文档第 6 节）。
    return sorted(out, key=_order_key)


def entry(entry_id: str):
    return _index().get(entry_id)


def path_of(entry_id: str) -> str:
    item = entry(entry_id)
    if not item:
        return ""
    path = os.path.join(ROOT, item["path"])
    return path if os.path.exists(path) else ""


def url_of(entry_id: str) -> str:
    path = path_of(entry_id)
    if not path:
        return ""
    return "file:///" + path.replace("\\", "/")
