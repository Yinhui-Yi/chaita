"""iteminfo 单元测试（`chaita/game/iteminfo.py`）。

真值来自 `assets/item_effects.json` + `assets/items/map.json`，不是抄代码输出。
"""

from chaita.game import iteminfo


def test_is_gem():
    assert iteminfo.is_gem("gem_red")
    assert iteminfo.is_gem("gem_purple")
    assert iteminfo.is_gem("gem_green")
    assert iteminfo.is_gem("gem_yellow")
    assert not iteminfo.is_gem("potion_red")
    assert not iteminfo.is_gem("")
    assert not iteminfo.is_gem("key_red")


def test_is_potion():
    assert iteminfo.is_potion("potion_red")
    assert iteminfo.is_potion("potion_purple")
    assert not iteminfo.is_potion("gem_red")
    # 没有图标名时按名字查：红血瓶 → potion_red
    assert iteminfo.is_potion("", "红血瓶")


def test_icon_for():
    assert iteminfo.icon_for("红宝石") == "gem_red"
    assert iteminfo.icon_for("蓝宝石") == "gem_purple"
    assert iteminfo.icon_for("红血瓶") == "potion_red"
    assert iteminfo.icon_for("铁盾") == "shield"
    assert iteminfo.icon_for("铁剑") == "sword"
    assert iteminfo.icon_for("红钥匙") == "key_red"
    # 名字里没有颜色 → 空串
    assert iteminfo.icon_for("不知道") == ""


def test_icon_for_gives_weapons_and_shields_a_picture_even_without_a_table_entry():
    """表里没有的剑/盾也要有缩略图（用户："我用刷新读取的剑和盾怎么没有缩略图"）。

    规则：名字精确对上用户指定表 / 全道具表 → 用那张；没对上就按**种类**兜底
    （武器 → sword，防具 → shield）。兜底那张图必须真在盘上。
    """
    for name in ("钢剑", "长剑", "圣剑", "剑", "屠龙刀"):
        stem = iteminfo.icon_for(name)
        assert stem == "sword", (name, stem)
        assert iteminfo.icon_exists(stem), stem
    for name in ("钢盾", "铁甲", "盾"):
        stem = iteminfo.icon_for(name)
        assert stem == "shield", (name, stem)
        assert iteminfo.icon_exists(stem), stem
    # 和种类无关的名字仍然不给图（别瞎贴一张剑）
    assert iteminfo.icon_for("木棍") == ""
    assert iteminfo.icon_for("普通石头") == ""


def test_kind_fallback_does_not_merge_two_different_swords():
    """兜底成同一张图**不代表是同一件东西**：长剑和钢剑各占一行。"""
    assert iteminfo.key_for("长剑") == "name:长剑"
    assert iteminfo.key_for("钢剑") == "name:钢剑"
    assert iteminfo.key_for("长剑") != iteminfo.key_for("钢剑")


def test_migrate_icon_renames_old_game_prefix():
    """老存档里带别的游戏/塔前缀的图标名，要换成现在的语义名。"""
    assert iteminfo.migrate_icon("xinxin2_sword1") == "sword"
    assert iteminfo.migrate_icon("h5_sword1") == "sword"
    assert iteminfo.migrate_icon("xinxin_sword1") == "sword"
    assert iteminfo.migrate_icon("xinxin2_redKey") == "key_red"
    assert iteminfo.migrate_icon("h5_shield1") == "shield"
    # 已经是新名字 / 中性名 / 不认识的，一律照原样
    assert iteminfo.migrate_icon("sword") == "sword"
    assert iteminfo.migrate_icon("gem_red") == "gem_red"
    assert iteminfo.migrate_icon("") == ""
    assert iteminfo.migrate_icon(None) == ""


def test_every_mapped_icon_file_exists():
    """map.json 里点到的每个图标都得真在 assets/items 里（加资源界面缩略图来源）。"""
    mapped = iteminfo.icon_map()
    assert mapped, "map.json 不能是空的"
    for stem in mapped.values():
        assert iteminfo.icon_exists(stem), stem


def test_key_for():
    # 同一个图标归一：红药水 / 红血瓶都是 potion_red
    assert iteminfo.key_for("红宝石") == "icon:gem_red"
    assert iteminfo.key_for("红药水") == "icon:potion_red"
    assert iteminfo.key_for("红血瓶") == "icon:potion_red"
    assert iteminfo.key_for("随便") == "name:随便"


def test_effect_for():
    assert iteminfo.effect_for("gem_red") == "攻击力 +1"
    assert iteminfo.effect_for("gem_purple") == "防御力 +1"
    assert iteminfo.effect_for("gem_green") == "魔防 +2"
    assert iteminfo.effect_for("gem_yellow") == "攻击力 +1 · 防御力 +1 · 魔防 +2"
    assert iteminfo.effect_for("potion_red") == "体力 +150"
    # 按名字查：红宝石 → gem_red → 攻击力 +1
    assert iteminfo.effect_for("", "红宝石") == "攻击力 +1"


def test_normalize_effect():
    assert iteminfo.normalize_effect("生命+2000") == "生命 +2000"
    assert iteminfo.normalize_effect("攻击力 + +1") == "攻击力 +1"
    assert iteminfo.normalize_effect("") == ""


def test_split_effect():
    # 单段：属性 + 数值
    assert iteminfo.split_effect("攻击力 +2") == ("攻击力", "+2")
    # 多段整句不拆（一个框只能改一个数）
    assert iteminfo.split_effect("攻击力 +1 · 防御力 +1") \
        == ("攻击力 +1 · 防御力 +1", "")
    # 没有数值的
    assert iteminfo.split_effect("可以打开一扇黄门") == ("可以打开一扇黄门", "")
    assert iteminfo.split_effect("") == ("", "")


def test_join_effect():
    assert iteminfo.join_effect("攻击力", "5") == "攻击力 +5"
    assert iteminfo.join_effect("攻击力", "-3") == "攻击力 -3"
    assert iteminfo.join_effect("攻击力", "") == "攻击力"


def test_split_effect_parts():
    assert iteminfo.split_effect_parts("攻击力 +1 · 防御力 +1 · 魔防 +2") == [
        ("攻击力", "+", "1"), ("防御力", "+", "1"), ("魔防", "+", "2")]
    assert iteminfo.split_effect_parts("攻击力 +2") == [("攻击力", "+", "2")]


def test_effect_with_part():
    # 只改第 1 段（防御力），其余段原样
    assert iteminfo.effect_with_part(
        "攻击力 +1 · 防御力 +1 · 魔防 +2", 1, "5") \
        == "攻击力 +1 · 防御力 +5 · 魔防 +2"


def test_kind_rank():
    assert iteminfo.kind_rank("红宝石", "gem_red") == 0      # 宝石
    assert iteminfo.kind_rank("铁剑", "sword") == 1  # 武器
    assert iteminfo.kind_rank("铁盾", "shield") == 2  # 防具
    assert iteminfo.kind_rank("红血瓶", "potion_red") == 3   # 血瓶
    assert iteminfo.kind_rank("红钥匙", "key_red") == 4  # 钥匙


def test_sort_items_gems_first_keys_last():
    rows = [
        {"name": "红钥匙", "icon": "key_red", "effect": ""},
        {"name": "红宝石", "icon": "gem_red", "effect": "攻击力 +1"},
        {"name": "铁盾", "icon": "shield", "effect": ""},
    ]
    ordered = [row["name"] for row in iteminfo.sort_items(rows)]
    assert ordered == ["红宝石", "铁盾", "红钥匙"]
