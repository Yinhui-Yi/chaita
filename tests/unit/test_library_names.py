"""素材文件名单元测试（`chaita/library_names.py`）。

真值来自用户定的口径：全 ASCII、种族+名字、带人名只写编号、弱的在前带序号。
"""

import chaita.library_names as ln


def test_has_proper_name():
    assert ln.has_proper_name("斗神·高巴")
    assert ln.has_proper_name("魔剑之凯撒")
    assert not ln.has_proper_name("史莱姆")


def test_clean_lowercases_and_underscores():
    assert ln.clean("Foo: Bar") == "foo_bar"
    assert ln.clean("A B/C") == "a_b_c"
    assert ln.clean("") == ""


def test_file_stem_race_plus_name():
    assert ln.file_stem("史莱姆", "绿色史莱姆") == "slime_green_slime"


def test_file_stem_keeps_same_as_race():
    # 用户："有的素材只有种族没有名字" 不该再发生 —— 名字照原样翻
    assert ln.file_stem("史莱姆", "史莱姆") == "slime_slime"


def test_file_stem_order_is_one_based_and_padded():
    assert ln.file_stem("史莱姆", "史莱姆", order=0) == "001_slime_slime"
    assert ln.file_stem("史莱姆", "史莱姆", order=72) == "073_slime_slime"


def test_file_stem_proper_name_uses_eid_not_person():
    # 带人名只写塔里的编号，不写人名
    assert ln.file_stem("守卫", "斗神·高巴", eid="guard_e380") \
        == "guard_guard_e380"
    assert ln.file_stem("守卫", "斗神·高巴", eid="guard_e380", order=72) \
        == "073_guard_guard_e380"


def test_file_stem_unknown_name_falls_back():
    # 名字表里没有：种族 + 调用方给的定位串，不能只剩种族
    assert ln.file_stem("史莱姆", "没见过的新怪", fallback="xinxin_E999") \
        == "slime_xinxin_e999"
