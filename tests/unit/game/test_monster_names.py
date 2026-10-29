"""monster_names 单元测试（`chaita/game/monster_names.py`）。

真值来自规则（文档里写的做法），不是抄代码输出。
"""

from chaita.game import monster_names


def test_normalize():
    assert monster_names.normalize("红 头 怪") == "红头怪"
    assert monster_names.normalize("红头怪！") == "红头怪"
    assert monster_names.normalize("Red Monster") == "redmonster"
    assert monster_names.normalize("") == ""


def test_match_one_exact():
    assert monster_names.match_one("红头怪", ["红头怪", "青头怪"]) == "红头怪"


def test_match_one_subsequence():
    # 读地图叫"红史莱姆"，手册是"红色史莱姆"：中间少个字 → 对上一只
    assert monster_names.match_one("红史莱姆", ["红色史莱姆"]) == "红色史莱姆"


def test_match_one_strict_requires_same_ends():
    # 严格模式（读手册用）：首尾字都要对得上
    assert monster_names.match_one("红史莱姆", ["红色史莱姆"], strict=True) \
        == "红色史莱姆"
    # "血蚊" ⊂ "血蚊王"，但尾字不同 → 不认
    assert monster_names.match_one("血蚊", ["血蚊王"], strict=True) == ""


def test_match_one_tie_returns_empty():
    # "史莱姆" 和红色/绿色史莱姆一样像 → 宁可漏，不记错
    assert monster_names.match_one("史莱姆", ["红色史莱姆", "绿色史莱姆"]) == ""


def test_match_one_unique_best():
    # "绿头怪" 对 "青头怪" 共同"头怪"，唯一最像 → 认
    assert monster_names.match_one("绿头怪", ["青头怪"]) == "青头怪"
    # 和谁都不像（共同字 < 2）→ 空
    assert monster_names.match_one("龙", ["青头怪"]) == ""


def test_align():
    mapping, unmatched, invented = monster_names.align(
        ["红史莱姆", "不认识的怪"], ["红色史莱姆", "绿色史莱姆"])
    assert mapping == {"红史莱姆": "红色史莱姆"}
    assert unmatched == ["不认识的怪"]
    assert invented == ["红史莱姆"]
