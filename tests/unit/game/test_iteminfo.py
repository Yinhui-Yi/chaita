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
    assert not iteminfo.is_gem("xinxin2_redKey")


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
    assert iteminfo.icon_for("铁盾") == "xinxin2_shield1"
    # 名字里没有颜色 → 空串
    assert iteminfo.icon_for("不知道") == ""


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
    assert iteminfo.kind_rank("铁剑", "xinxin2_sword1") == 1  # 武器
    assert iteminfo.kind_rank("铁盾", "xinxin2_shield1") == 2  # 防具
    assert iteminfo.kind_rank("红血瓶", "potion_red") == 3   # 血瓶
    assert iteminfo.kind_rank("红钥匙", "xinxin2_redKey") == 4  # 钥匙


def test_sort_items_gems_first_keys_last():
    rows = [
        {"name": "红钥匙", "icon": "xinxin2_redKey", "effect": ""},
        {"name": "红宝石", "icon": "gem_red", "effect": "攻击力 +1"},
        {"name": "铁盾", "icon": "xinxin2_shield1", "effect": ""},
    ]
    ordered = [row["name"] for row in iteminfo.sort_items(rows)]
    assert ordered == ["红宝石", "铁盾", "红钥匙"]
