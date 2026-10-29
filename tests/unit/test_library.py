"""素材库规则单元测试（`chaita/library.py`）。

真值来自用户定的口径：颜色档位蓝<绿<黄<红<黑、分类先看贴图表再名字再英文 id、
power = hp + 10*(攻+防)、单只的族折进「其他」、文件名全 ASCII。
"""

import chaita.library as lib


def test_kind_of_eid_override_first():
    # 名字看不出、看图定的：blackKing 是魔法师
    assert lib.kind_of("blackKing", "黑衣魔王") == "魔法师"


def test_kind_of_by_name():
    assert lib.kind_of("", "绿色史莱姆") == "史莱姆"


def test_kind_of_by_english_id():
    assert lib.kind_of("greenSlime", "") == "史莱姆"


def test_kind_of_unknown_is_empty():
    assert lib.kind_of("", "没见过") == ""


def test_power_of():
    assert lib.power_of(100, 10, 20) == 400
    assert lib.power_of(0, 0, 0) is None
    assert lib.power_of("x", 0, 0) is None


def test_hidden():
    assert lib._hidden({"name": "新敌人"}) is True
    assert lib._hidden({"name": "毒龙（已弃用）"}) is True
    assert lib._hidden({"name": "血蚊"}) is False


def test_common_suffix():
    assert lib._common_suffix("史莱姆王", "白银史莱姆王") == "史莱姆王"
    assert lib._common_suffix("abc", "xyz") == ""


def test_family_of_visual_group_first():
    assert lib.family_of("绿色史莱姆") == "看:0"
    assert lib.family_of("没见过") == "名:没见过"


def test_position_of():
    assert lib.position_of({"eid": "greenSlime"}) == 0
    assert lib.position_of({"eid": "不存在的id"}) == lib.UNKNOWN_POS


def test_display_name():
    assert lib.display_name({"name": "血蚊"}) == "血蚊"
    assert lib.display_name({"name": "", "id": "monster/xinxin_E380"}) \
        == "xinxin_E380"


def test_order_key():
    assert lib._order_key({"order": 5, "id": "x"}) == (0, 5, "")
    assert lib._order_key({"id": "monster/a"}) == (1, 0, "monster/a")


def test_file_stem():
    entry = {"tower": "xinxin", "eid": "greenSlime", "name": "绿色史莱姆",
             "order": 0}
    assert lib.file_stem(entry) == "001_slime_green_slime"


def test_normalized_adds_kind_power_pos():
    rows = [{"name": "绿色史莱姆", "eid": "greenSlime", "hp": "100",
             "atk": "10", "def": "20"}]
    out = lib._normalized(rows)
    assert out[0]["kind"] == "史莱姆"
    assert out[0]["power"] == 400
    assert out[0]["pos"] == 0
    assert "kind" not in rows[0]        # 不改原数据


def test_fold_singletons_into_other():
    items = [{"kind": "史莱姆", "name": "a"},
             {"kind": "史莱姆", "name": "b"},
             {"kind": "骷髅", "name": "c"}]
    out = lib._fold_singletons(items)
    assert out[2]["kind"] == "其他"


def test_arrange_without_order_sorts_by_power():
    rows = [
        {"name": "绿色史莱姆", "eid": "greenSlime", "hp": "100", "atk": "10",
         "def": "20", "tower": "xinxin"},
        {"name": "红色史莱姆", "eid": "redSlime", "hp": "120", "atk": "10",
         "def": "20", "tower": "xinxin"},
    ]
    out = lib.arrange(rows)
    assert [one["name"] for one in out] == ["绿色史莱姆", "红色史莱姆"]
    assert out[0]["order"] == 0
    assert out[1]["order"] == 1


def test_arrange_respects_existing_order():
    rows = [
        {"name": "b", "eid": "x", "hp": "1", "atk": "1", "def": "1",
         "order": 1},
        {"name": "a", "eid": "y", "hp": "1", "atk": "1", "def": "1",
         "order": 0},
    ]
    out = lib.arrange(rows)
    assert [one["name"] for one in out] == ["a", "b"]   # 已有 order 就照它


def test_id_of_file_direct_key(monkeypatch):
    monkeypatch.setattr(lib, "_index",
                        lambda: {"monster/xinxin_greenSlime":
                                 {"name": "绿色史莱姆", "eid": "greenSlime",
                                  "tower": "xinxin"}})
    assert lib.id_of_file("xinxin_greenSlime") == "monster/xinxin_greenSlime"


# ---- 文件 I/O 与派生查询：stub load/open ----

def test_load_reads_and_arranges(monkeypatch):
    import io
    import json
    payload = json.dumps({"items": [
        {"name": "血蚊", "eid": "x", "hp": "1", "atk": "1", "def": "1",
         "tower": "xinxin", "order": 0},
    ]}, ensure_ascii=False)
    monkeypatch.setattr(lib.os.path, "getmtime", lambda p: 123)
    opened = []

    def fake_open(*a, **k):
        opened.append(1)
        return io.StringIO(payload)

    monkeypatch.setattr("builtins.open", fake_open)
    lib._CACHE.clear()
    data = lib.load()
    assert data["count"] == 1
    assert data["items"][0]["name"] == "血蚊"
    # 第二次走缓存：mtime 没变就不再读文件
    assert lib.load()["count"] == 1
    assert len(opened) == 1


def test_load_missing_file_is_empty(monkeypatch):
    monkeypatch.setattr(lib.os.path, "getmtime",
                        lambda p: (_ for _ in ()).throw(OSError("no")))
    lib._CACHE.clear()
    assert lib.load() == {"count": 0, "items": []}


def test_items_filters_and_sorts(monkeypatch):
    monkeypatch.setattr(lib, "load", lambda: {"items": [
        {"category": "monster", "order": 1, "id": "a"},
        {"category": "item", "order": 0, "id": "b"},
        {"category": "monster", "order": 0, "id": "c"},
    ]})
    out = lib.items("monster")
    assert [e["id"] for e in out] == ["c", "a"]


def test_pictures_dedups_frames_and_hidden(monkeypatch):
    monkeypatch.setattr(lib, "items", lambda category=None: [
        {"id": "monster/x_0", "category": "monster", "name": "血蚊",
         "order": 0},
        {"id": "monster/x_1", "category": "monster", "name": "血蚊",
         "order": 1},
        {"id": "monster/y", "category": "monster", "name": "新敌人",
         "order": 2},
    ])
    out = lib.pictures("monster")
    assert [e["id"] for e in out] == ["monster/x_0"]


def test_pictures_adds_aliases(monkeypatch):
    monkeypatch.setattr(lib, "items", lambda category=None: [
        {"id": "monster/a", "category": "monster", "name": "自己",
         "names": ["自己", "迷失勇者"], "order": 0},
    ])
    out = lib.pictures("monster")
    assert "迷失勇者" in out[0]["aliases"]


def test_index_maps_id_and_aliases(monkeypatch):
    monkeypatch.setattr(lib, "load", lambda: {"items": [
        {"id": "monster/a", "alias_ids": ["monster/b"], "name": "x"},
    ]})
    lib._CACHE["stamp"] = "S"
    lib._CACHE.pop("index", None)
    idx = lib._index()
    assert "monster/a" in idx
    assert idx["monster/b"]["name"] == "x"


def test_path_of_and_url_of(monkeypatch):
    monkeypatch.setattr(lib, "entry",
                        lambda eid: {"path": "assets/library/monster/x.png"}
                        if eid == "monster/a" else None)
    monkeypatch.setattr(lib.os.path, "exists", lambda p: True)
    assert lib.path_of("monster/a").endswith("x.png")
    assert lib.url_of("monster/a").startswith("file:///")
    assert lib.path_of("monster/nope") == ""
    assert lib.url_of("monster/nope") == ""


# ---- 同类型号：后缀优先，后缀不成才看前缀 ----

def test_common_prefix():
    assert lib._common_prefix("魔法师首领", "魔法师元帅") == "魔法师"
    assert lib._common_prefix("abc", "xyz") == ""


def test_family_key_prefers_suffix_then_prefix():
    assert lib._family_key("史莱姆王", "白银史莱姆王") == (0, "史莱姆王")
    assert lib._family_key("魔法师首领", "魔法师元帅") == (1, "魔法师")
    assert lib._family_key("血蚊", "铁卫") is None


def test_family_of_links_same_model():
    label = lib._family_of(["史莱姆王", "白银史莱姆王", "白银史莱姆"])
    # 同一个"型号"的（王冠那批）归一家，颜色前缀不把白银史莱姆王拽走
    assert label["史莱姆王"] == label["白银史莱姆王"]
    assert label["白银史莱姆"] != label["史莱姆王"]


def test_family_of_prefix_family_and_default():
    label = lib._family_of(["魔法师首领", "魔法师元帅", "旁观者"])
    assert label["魔法师首领"] == label["魔法师元帅"]
    assert label["旁观者"] == "旁观者"        # 谁都挨不上就自己一家


# ---- 建库规则：种族的整体挪动（用户点名过的顺序）----

def _row(name, power_hp=100, tower="xinxin", eid=None):
    return {"name": name, "eid": eid or name, "tower": tower,
            "hp": str(power_hp), "atk": "10", "def": "10"}


def test_kind_after_puts_block_behind_host(monkeypatch):
    """机制：整块种族挪到宿主种族**后面**（表里填哪两个是数据，不是规则）。"""
    monkeypatch.setattr(lib, "KIND_AFTER", {"弓兵": "骑士"})
    out = lib.arrange([_row("弓兵"), _row("骑士")])
    assert [one["name"] for one in out] == ["骑士", "弓兵"]


def test_kind_after_without_host_changes_nothing(monkeypatch):
    monkeypatch.setattr(lib, "KIND_AFTER", {"弓兵": "根本没这个种族"})
    out = lib.arrange([_row("弓兵"), _row("骑士")])
    assert {one["name"] for one in out} == {"弓兵", "骑士"}


def test_kind_before_puts_block_before_host(monkeypatch):
    """机制：整块挪到宿主种族**前面**；真实数据里是「勇者放公主前」。"""
    out = lib.arrange([_row("公主"), _row("勇者")])
    assert [one["name"] for one in out] == ["勇者", "公主"]


def test_arrange_handles_unknown_names():
    """看图表里没有的名字：退回按名字分家，不能炸。"""
    out = lib.arrange([_row("没见过的甲"), _row("没见过的乙")])
    assert len(out) == 2
    assert [one["order"] for one in out] == [0, 1]


# ---- 读 manifest 的坏数据 ----

def test_load_bad_json_is_empty(monkeypatch):
    import io
    monkeypatch.setattr(lib.os.path, "getmtime", lambda p: 555)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO("{不是 json"))
    lib._CACHE.clear()

    assert lib.load() == {"count": 0, "items": []}
    # 坏数据也记 stamp：同一个坏文件不用反复解析
    assert lib._CACHE["stamp"] == 555


def test_load_non_dict_payload_is_empty(monkeypatch):
    import io
    import json
    monkeypatch.setattr(lib.os.path, "getmtime", lambda p: 556)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO(json.dumps(["列表"])))
    lib._CACHE.clear()

    assert lib.load() == {"count": 0, "items": []}


def test_load_drops_non_dict_entries(monkeypatch):
    import io
    import json
    monkeypatch.setattr(lib.os.path, "getmtime", lambda p: 557)
    payload = json.dumps({"items": ["坏的",
                                    {"name": "血蚊", "eid": "x", "tower": "t",
                                     "hp": "1", "atk": "1", "def": "1",
                                     "order": 0}]},
                         ensure_ascii=False)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO(payload))
    lib._CACHE.clear()

    data = lib.load()
    assert data["count"] == 1
    assert data["items"][0]["name"] == "血蚊"


# ---- 显示名 / 文件名 / 反查 ----

def test_display_name_and_file_stem_reject_non_dict():
    assert lib.display_name("不是 dict") == ""
    assert lib.file_stem(None) == "icon"


def test_id_of_file_variants(monkeypatch):
    entries = {
        "monster/a": {"id": "monster/a", "name": "绿色史莱姆",
                      "eid": "greenSlime", "tower": "xinxin", "order": 1},
    }
    monkeypatch.setattr(lib, "_index", lambda: entries)
    stem = lib.file_stem(entries["monster/a"])

    assert lib.id_of_file(stem) == "monster/a"                 # 现在这个名字
    assert lib.id_of_file(lib._ORDER_PREFIX.sub("", stem)) == "monster/a"
    assert lib.id_of_file("绿色史莱姆") == "monster/a"          # 老的中文名
    assert lib.id_of_file("") == ""
    assert lib.id_of_file("完全查不到") == ""


# ---- 调顺序的表：写的种族必须在素材库里真的有，否则那条规则永远不执行 ----

def test_ordering_tables_reference_kinds_that_exist():
    """`KIND_AFTER/KIND_BEFORE/KIND_PLACE` 里写错一个名字，那条顺序就**静默失效**。

    拿素材库真实数据核对（表里的种族 = manifest 里出现过的 kind）；素材库还没建
    （manifest 为空）时跳过。
    """
    import pytest

    kinds = {str(one.get("kind") or "") for one in lib.items()}
    kinds.discard("")
    if not kinds:
        pytest.skip("素材库还没建（manifest 为空），没法核对")

    referenced = set()
    referenced |= set(lib.KIND_AFTER) | set(lib.KIND_AFTER.values())
    referenced |= set(lib.KIND_BEFORE) | set(lib.KIND_BEFORE.values())
    referenced |= set(lib.KIND_PLACE)

    missing = sorted(name for name in referenced if name not in kinds)
    assert missing == [], "这些种族在素材库里不存在，写了也不会生效：%s" % missing
