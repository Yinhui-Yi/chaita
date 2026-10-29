"""界面文本拆分单元测试（`chaita/ui/toolkit/texts.py`）。

真值来自规则：状态拆三段（属性/道具/金币经验）、重建行时带过用户自加字段、
层数只留可显示字符串。
"""

import chaita.ui.toolkit.texts as tx


def test_split_status_full():
    status = {"hp": 1000, "atk": 90, "def": 30, "mdef": 10,
              "keys": {"yellow": 2, "blue": 1, "red": 0},
              "special": {"po": 1, "zha": 0, "fei": 3},
              "gold": 500, "exp": 12, "next": 20}
    attr, items, gold = tx._split_status(status)
    assert attr == "生命 1000   攻击 90   防御 30   魔防 10"
    assert items == "钥匙 黄2 蓝1 红0   破1 炸0 飞3"
    assert gold == "金币 500   经验 12   升级还需 20"


def test_split_status_skips_non_numeric_keys():
    status = {"keys": {"yellow": "x", "blue": 2}}
    attr, items, gold = tx._split_status(status)
    assert "黄" not in items       # 非数字的钥匙不显示
    assert "蓝2" in items


def test_split_status_non_dict():
    attr, items, gold = tx._split_status("oops")
    assert attr == "oops"
    assert items == ""
    assert gold == ""


def test_carry_row_copies_user_extra_keys():
    old = {"icon": "a.png", "done": True, "effect_manual": "x", "count": 3}
    new = {"name": "血蚊", "count": 5}
    out = tx._carry_row(old, new)
    assert out["icon"] == "a.png"
    assert out["done"] is True
    assert out["effect_manual"] == "x"
    assert out["count"] == 5        # new 已有的值不被覆盖


def test_floor_text():
    assert tx._floor_text("1") == "1"
    assert tx._floor_text(1) == "1"
    assert tx._floor_text(1.5) == "1.5"
    assert tx._floor_text(None) == ""
    assert tx._floor_text(True) == ""
    assert tx._floor_text("null") == ""
    assert tx._floor_text("未知") == ""
    assert tx._floor_text("") == ""
