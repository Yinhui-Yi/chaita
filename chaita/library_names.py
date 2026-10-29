"""素材文件名怎么起：**编号 + 种族 + 名字，全 ASCII**。

用户定的口径（原话）：

  · "种族加名字，并且禁止使用中文" —— 先写种族（`knight` 那一套看得懂的英文词），
    再写名字；
  · "禁止使用拼音" —— 名字不能是 `shilaimu`、`kulou` 这种拼音，该意译的意译
    （史莱姆→`slime`、骷髅巫师→`skeleton_wizard`）；
  · "给素材名字里加ID确保弱的在前面" —— 文件名最前面加**显示序号**
    （`order`，就是界面上「同族相连、弱的在前」的顺序）：资源管理器里按名字排序，
    看到的就是"弱 → 强"；
  · "这些人名都是仅限于新新魔塔的，作为素材应该直接删掉，用编号" ——
    名字里带人名的（`斗神·高巴`、`剑神·沙士`、`魔剑之凯撒`、`灵盾之柏奇`、
    `魔神·些多`、`魔界之王·古顿`、`魔王·格勒第`、`箭神·法比`）**不写人名**，
    名字那截只留塔里的编号（`073_guard_e380`）。

文件名只给人看和排错（`chaita/library.py::file_stem` 是唯一入口）：
代码取图走 manifest 的 `path` 和 `id`（`monster/<塔>_<贴图键>`）——
`id` 是存档和 `icon_id` 的稳定键，改名不动它。

新增素材时，名字表里没有就退回 `<种族>_<贴图键>.png`；`tests/test_names.py`
会盯住"manifest 里每一只都有英文名"，漏了直接红。
"""

import re

# ---- 种族（`chaita/library.py` 的类名）→ 英文 ----
KIND_ASCII = {
    "史莱姆": "slime",
    "史莱姆人": "slime_man",
    "蝙蝠": "bat",
    "骷髅": "skeleton",
    "丧尸": "zombie",
    "石怪": "rock",
    "长袍魔法师": "robed_mage",
    "术士": "warlock",
    "法师": "mage",
    "守卫": "guard",
    "剑士": "swordsman",
    "骑士": "knight",
    "死灵": "undead",
    "魔法师": "magician",
    "魔神": "demon_god",
    "魔王": "demon_king",
    "勇者": "hero",
    "公主": "princess",
    "仙子": "fairy",
    "幽灵": "ghost",
    "龙": "dragon",
    "八爪鱼": "octopus",
    "天使": "angel",
    "元素": "elemental",
    "弓兵": "archer",
    "植物": "plant",
    "灵": "spirit",
    "矮人": "dwarf",
    "眼": "eye",
    "马": "horse",
    "其他": "other",
}

# ---- 怪物名 → 英文（种族那截由 file_stem 拼在前面） ----
NAME_ASCII = {
    # 史莱姆
    "史莱姆": "slime",
    "绿色史莱姆": "green_slime",
    "红色史莱姆": "red_slime",
    "黑色史莱姆": "black_slime",
    "黄金史莱姆": "gold_slime",
    "白银史莱姆": "silver_slime",
    "邪眼史莱姆": "evil_eye_slime",
    "史莱姆阿修罗": "asura",
    "史莱姆王": "slime_king",
    "黄金史莱姆王": "gold_slime_king",
    "白银史莱姆王": "silver_slime_king",
    "金角怪": "gold_horn",
    "尖角怪": "sharp_horn",
    # 蝙蝠
    "蝙蝠": "bat",
    "大蝙蝠": "big_bat",
    "红蝙蝠": "red_bat",
    "毒蝙蝠": "poison_bat",
    "邪恶蝙蝠": "evil_bat",
    "龙蝠": "dragon_bat",
    # 骷髅
    "骷髅": "skeleton",
    "骷髅兵": "skeleton_soldier",
    "中级骷髅兵": "mid_skeleton_soldier",
    "高级骷髅兵": "high_skeleton_soldier",
    "不死骷髅兵": "undead_skeleton_soldier",
    "重生骷髅兵": "reborn_skeleton_soldier",
    "骷髅队长": "skeleton_captain",
    "骷髅头目": "skeleton_leader",
    "骷髅武士": "skeleton_warrior",
    "骷髅战士": "skeleton_fighter",
    "骷髅王": "skeleton_king",
    "骷髅剑士": "skeleton_swordsman",
    "骷髅法师": "skeleton_mage",
    "骷髅巫师": "skeleton_wizard",
    "灵骷髅": "spirit_skeleton",
    "灵骷髅兵": "spirit_skeleton_soldier",
    "冻死骨": "frozen_bone",
    # 丧尸
    "丧尸": "zombie",
    "丧尸剑士": "zombie_swordsman",
    "丧尸士兵": "zombie_soldier",
    "毒丧尸": "poison_zombie",
    "烈焰丧尸": "flame_zombie",
    # 石怪
    "石怪": "rock",
    "石头怪": "stone_rock",
    "铁怪": "iron_rock",
    "鬼邪石": "evil_stone",
    # 史莱姆人
    "史莱姆人": "slime_man",
    "四手史莱姆人": "four_arm_slime_man",
    "蓝色长袍魔法师": "blue",
    "黄色长袍魔法师": "yellow",
    "红色长袍魔法师": "red",
    "黑色长袍魔法师": "black",
    # 术士
    "魔法师": "magician",
    "魔术师": "conjurer",
    "炎术士": "flame_warlock",
    "雷术士": "thunder_warlock",
    "混沌术士": "chaos_warlock",
    # 法师
    "大法师": "archmage",
    "红衣大法师": "red_archmage",
    "火炎大法师": "flame_archmage",
    "极地法师": "polar_mage",
    "魔神法师": "demon_god_mage",
    # 守卫
    "守卫": "guard",
    "中级守卫": "mid_guard",
    "高级守卫": "high_guard",
    "铁守卫": "iron_guard",
    # 骑士
    "骑士": "knight",
    "双手剑士": "two_hand_swordsman",
    "双手剑兵": "two_hand_sword_soldier",
    "灵武士": "spirit_warrior",
    "不死战士": "undead_fighter",
    "皇室枪兵": "royal_spearman",
    "皇室剑士": "royal_swordsman",
    "血剑士": "blood_swordsman",
    "近卫骑士": "bodyguard_knight",
    "铁骑士": "iron_knight",
    "强盾骑士": "strong_shield_knight",
    "剑圣": "sword_saint",
    "剑王": "sword_king",
    # 死灵
    "死灵战士": "undead_warrior",
    "死灵大法师": "undead_archmage",
    "死灵术士": "undead_warlock",
    # 魔法师
    "魔法师首领": "magician_leader",
    "魔法师元帅": "magician_marshal",
    "上级魔法师": "high_magician",
    "中级魔法师": "mid_magician",
    "暗黑魔法师": "dark_magician",
    "黑衣魔王": "black_cloak_demon_king",
    "黑魔王": "black_demon_king",
    "魔王": "demon_king",
    "魔王近卫兵": "demon_king_guard",
    "大魔王": "great_demon_king",
    # 魔王
    "魔神武士": "demon_god_warrior",
    "恶魔首领": "demon_leader",
    # 勇者
    "自己": "self",
    "迷失勇者": "lost_hero",
    # 公主
    "假公主": "fake_princess",
    "痛苦魔女": "agony_witch",
    # 仙子
    "仙子": "fairy",
    "黑暗妖精": "dark_sprite",
    "黑暗仙子": "dark_fairy",
    # 幽灵
    "水银人": "quicksilver_man",
    # 龙
    "恶龙": "evil_dragon",
    "巨龙": "giant_dragon",
    "毒龙": "poison_dragon",
    "毒龙（已弃用）": "poison_dragon_deprecated",
    "黄金龙": "golden_dragon",
    # 八爪鱼
    "八爪鱼": "octopus",
    "巨型八爪鱼": "giant_octopus",
    "魔界八爪鱼": "demon_octopus",
    "毒八爪鱼": "poison_octopus",
    "闪光八爪鱼": "flash_octopus",
    # 天使 / 元素 / 弓兵 / 植物 / 灵 / 矮人 / 眼 / 马 / 其他
    "天使": "angel",
    "元素生物": "elemental_creature",
    "弓兵": "archer",
    "精锐弓兵": "elite_archer",
    "触手植物": "tentacle_plant",
    "触手魔物": "tentacle_monster",
    "生气灵": "living_spirit",
    "冥界矮人战士": "underworld_dwarf_warrior",
    "魔眼": "demon_eye",
    "地狱马": "hell_horse",
    "新敌人": "new_enemy",
    "血使者": "blood_envoy",
}

# ---- 看图改名（用户："一张一张看素材的图，并给素材命名"） ----
# 塔里的名字大部分跟图对得上；这里记的是**看着图不对、按图改**的那几条。
# 键是 `(塔, 贴图键)`，值是看图后的名字。
ART_NAMES = {
    # 用户："种族改成长袍魔法师，蓝的初级，黄的中级，红的高级，黑的混沌"
    # 用户："既然守卫原来用的颜色，那现在法师也用颜色吧"
    ("xinxin", "bluePriest"): "蓝色长袍魔法师",     # 蓝紫袍
    ("xinxin", "grayPriest"): "黄色长袍魔法师",     # 米黄袍
    ("xinxin", "redPriest"): "红色长袍魔法师",      # 红袍
    ("xinxin2", "skeletonPriest"): "黑色长袍魔法师",  # 灰黑袍
    # 2026-10：这里本来把 xinxin 的 E336 改成「绿色史莱姆」，是我看图看快了 ——
    # 那格画的不是圆史莱姆，改回去按塔里的原名（毒龙），等你看过再定。
}

# 同一张画、两个名字的：**只并这几组**（用户点出来的重复）。
# `键` 是留下来的那只 `(塔, 贴图键)`，值是并进来的那些。
# 不按"轮廓一样"批量并 —— 那样连红色史莱姆/骑士都被并掉（用户："错的东西太多了"），
# 换色的怪到底算不算重复，只能一张张看图定。
ART_MERGES = {
    # 用户："021，022重复的看不出来吗" —— 骷髅队长 / 骷髅头目 是同一张画换色
    ("xinxin", "skeletonCaptain"): [("xinxin2", "poisonSkeleton")],
    # 用户："019，027也是重复的" —— 骷髅兵 / 骷髅剑士
    ("xinxin", "skeletonSoilder"): [("xinxin2", "skeletonSoilder")],
    # 自己 / 迷失勇者 是同一只勇者（两座塔各画一版）
    ("xinxin", "badHero"): [("xinxin2", "badHero")],
    # 毒蝙蝠：xinxin2 那张是干净的 30×23，xinxin 那张是 32×32 带棋盘底纹 —— 留干净的
    ("xinxin2", "poisonBat"): [("xinxin", "poisonBat")],
    # 毒丧尸：同上，xinxin2 干净（30×31），xinxin 那张带棋盘底纹
    ("xinxin2", "poisonZombie"): [("xinxin", "poisonZombie")],
    # 石怪：xinxin2 干净（32×26），xinxin 那张 32×32 带棋盘底纹 —— 留干净的
    ("xinxin2", "rock"): [("xinxin", "rock")],
    # 用户："046删掉" —— 红衣大法师 / 火炎大法师 是同一张画，留火炎大法师
    ("xinxin2", "redWizard"): [("xinxin", "redWizard")],
    # 用户："058 / 059 删有背景的" —— 剑王两只，删带棋盘底纹的 xinxin 版，留干净的 xinxin2 版
    ("xinxin2", "redSwordsman"): [("xinxin", "redSwordsman")],
    # 用户："里面这么多重复的看不出来" —— 魔法师族 4 对同一张画，删带底纹/重复的那份：
    ("xinxin2", "greenKing"): [("xinxin", "greenKing")],    # 魔法师元帅
    ("xinxin2", "yellowKing"): [("xinxin", "yellowKing")],  # 魔王近卫兵 / 魔王
    ("xinxin2", "redKing"): [("xinxin", "redKing")],        # 魔王 / 大魔王
    ("xinxin2", "blackKing"): [("xinxin", "blackKing")],    # 黑衣魔王 / 黑魔王
    # 毒龙：xinxin 干净（32×31、不透明 0.64），xinxin2 那张 32×32 带棋盘底纹（1.00）
    # 实测缩放后完全相同 64.4%，同一张画 —— 删带底纹那张
    ("xinxin", "E336"): [("xinxin2", "E432")],
}

# 文件名里不能出现的字符（Windows 最严）
_BAD_FILENAME = re.compile(r'[\\/:*?"<>|]')

# 人名（音译过来的专名）：只在新新魔塔里出现，出了这两座塔就没意义，
# 所以文件名里不写它，名字那截用塔里的编号（`guard_e380`）
PROPER_NAMES = ("高巴", "沙士", "凯撒", "柏奇", "些多", "古顿", "格勒第", "法比")


def has_proper_name(name: str) -> bool:
    """这名字里有人名吗（`斗神·高巴`、`魔剑之凯撒`、`魔王·格勒第`）。"""
    text = str(name or "")
    return any(word in text for word in PROPER_NAMES)


def clean(text: str) -> str:
    """`Foo: Bar` → `foo_bar`：小写、去非法字符、空白换下划线。"""
    text = _BAD_FILENAME.sub("_", str(text or "")).strip()
    text = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_")
    return text.lower()


def file_stem(kind: str, name: str, eid: str = "", order=None,
              fallback: str = "icon") -> str:
    """`编号_种族_名字`：`001_slime_green_slime`、`073_guard_e380`。

    - 编号是**显示序号**（`order`，0 起）：界面上的顺序是"同族相连、弱的在前"，
      带上它，资源管理器里按名字排序看到的也是"弱 → 强"
      （用户："给素材名字里加ID确保弱的在前面"）；
    - 名字里带人名的只写塔里的编号（用户："这些人名……用编号"）；
    - 名字照原样翻（`slime` 就叫 `slime`，不再因为"跟种族一样"被抹掉，
      用户："怎么有的素材只有种族没有名字"）。

    表里查不到的（以后新加的塔）退回 `fallback`（调用方给 `<塔>_<贴图键>`），
    至少还是 ASCII、能唯一定位。
    """
    race = KIND_ASCII.get(str(kind or ""), "")
    if has_proper_name(name):
        given = clean(eid)
    else:
        given = NAME_ASCII.get(str(name or ""), "")
    if not given:
        # 名字表里没有（以后新加的塔）：种族 + 调用方给的定位串，
        # **不能只剩一个种族**（那样同族的新怪全撞在一起）
        tail = clean(fallback)
        return clean("_".join(part for part in (race, tail) if part)) or "icon"
    parts = [race, given]
    stem = clean("_".join(part for part in parts if part)) or "icon"
    if order is None:
        return stem
    return "%03d_%s" % (int(order) + 1, stem)
