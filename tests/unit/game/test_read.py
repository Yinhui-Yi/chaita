"""读取结果纯函数单元测试（`chaita/game/read.py`）。

真值来自规则：parse_status 剥代码块、字段 0 不能当"没有"、资源列表归一化。
"""

import numpy as np

import chaita.game.read as gr


def test_parse_status_strips_code_fence():
    raw = '```json\n{"hp": 1000}\n```'
    assert gr.parse_status(raw) == {"hp": 1000}


def test_parse_status_plain_object():
    assert gr.parse_status('{"hp": 1000}') == {"hp": 1000}


def test_parse_status_garbage_marks_error():
    out = gr.parse_status("not json")
    assert out["_error"] == "无法解析模型输出"
    assert out["_raw"] == "not json"


def test_field_text_keeps_zero():
    assert gr._field_text(0) == "0"
    assert gr._field_text(0.0) == "0"
    assert gr._field_text(1.5) == "1.5"


def test_field_text_none_bool_and_null():
    assert gr._field_text(None) == ""
    assert gr._field_text(True) == ""
    assert gr._field_text("null") == ""
    assert gr._field_text("  abc  ") == "abc"


def test_normalize_items():
    items = [
        {"name": "红宝石", "effect": "攻击力 +1", "count": "3"},
        {"name": "血瓶", "count": True, "effect": ""},
        {"name": "", "count": 1},
        "not a dict",
    ]
    out = gr._normalize_items(items)
    assert len(out) == 2
    assert out[0]["name"] == "红宝石"
    assert out[0]["count"] == 3
    assert out[0]["icon"] == "gem_red"       # icon_for(红宝石)
    assert out[1]["count"] is None            # bool → None
    assert out[1]["name"] == "血瓶"


def test_normalize_items_non_list_is_empty():
    assert gr._normalize_items(None) == []
    assert gr._normalize_items("x") == []


def test_focus_map_none_or_empty_returns_as_is():
    assert gr.focus_map(None) is None
    empty = np.zeros((0, 0, 3), np.uint8)
    assert gr.focus_map(empty, 800) is empty


def test_focus_map_no_resize_when_narrow():
    img = np.zeros((100, 400, 3), np.uint8)
    assert gr.focus_map(img, 800) is img


def test_focus_map_resizes_when_wide(monkeypatch):
    import cv2
    resized = []
    monkeypatch.setattr(cv2, "resize",
                        lambda im, size, interpolation:
                        (resized.append(size), im)[1])
    img = np.zeros((100, 1600, 3), np.uint8)
    out = gr.focus_map(img, 800)
    assert out is img
    assert resized[-1] == (800, 50)      # 100 * 800/1600


def test_reading_str():
    status = gr.Reading(status={"hp": 1}, map=None, kind="status")
    assert "状态" in str(status)
    mons = gr.Reading(status={}, map=None, kind="monsters", monsters=[{}, {}])
    assert "2 只" in str(mons)


# ---- AI 编排：stub _ask_model/_ask，只测"怎么解析、怎么转发" ----


def test_screen_key_explicit_and_env(monkeypatch):
    assert gr._screen_key("sk-x") == "sk-x"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env")
    assert gr._screen_key(None) == "sk-env"


def test_screen_key_missing_raises(monkeypatch):
    import pytest

    import chaita.config as config
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(config, "api_key", lambda: "")
    with pytest.raises(RuntimeError):
        gr._screen_key(None)


def test_ask_parses_and_keeps_raw(monkeypatch):
    monkeypatch.setattr(gr, "_ask_model",
                        lambda p, image, api_key=None, max_tokens=None:
                        '{"hp": 1}')
    out = gr._ask("k", "p", None)
    assert out["hp"] == 1
    assert out["_raw"] == '{"hp": 1}'


def test_ask_retries_when_empty(monkeypatch):
    calls = []

    def fake(p, image, api_key=None, max_tokens=None):
        calls.append(1)
        return "" if len(calls) < 2 else '{"ok": 1}'

    monkeypatch.setattr(gr, "_ask_model", fake)
    out = gr._ask("k", "p", None, tries=2)
    assert out["ok"] == 1
    assert len(calls) == 2


def test_classify_manual_and_default(monkeypatch):
    monkeypatch.setattr(gr, "_ask",
                        lambda k, p, image, tries=3: {"screen": "manual"})
    assert gr.classify(None, "k") == "manual"
    monkeypatch.setattr(gr, "_ask",
                        lambda k, p, image, tries=3: {"screen": "map"})
    assert gr.classify(None, "k") == "map"


def test_classify_reads_raw_when_no_screen(monkeypatch):
    monkeypatch.setattr(gr, "_ask",
                        lambda k, p, image, tries=3: {"_raw": "MANUAL page"})
    assert gr.classify(None, "k") == "manual"


def test_read_floor(monkeypatch):
    monkeypatch.setattr(gr, "_ask",
                        lambda k, p, image, tries=3: {"floor": "地下30"})
    assert gr.read_floor(None, "k") == "地下30"
    monkeypatch.setattr(gr, "_ask",
                        lambda k, p, image, tries=3: {"floor": None})
    assert gr.read_floor(None, "k") == ""


def test_read_status(monkeypatch):
    monkeypatch.setattr(gr, "_ask",
                        lambda k, p, image, tries=3: {"hp": 1000})
    assert gr.read_status(None, "k") == {"hp": 1000}
    monkeypatch.setattr(gr, "_ask",
                        lambda k, p, image, tries=3: {"level": 1})
    assert gr.read_status_extra(None, "k") == {"level": 1}


def test_read_person_merges_extra(monkeypatch):
    monkeypatch.setattr(gr, "read_status",
                        lambda image, api_key=None: {"hp": "1000", "level": ""})
    monkeypatch.setattr(gr, "read_status_extra",
                        lambda image, api_key=None: {"level": "10",
                                                     "gold": "500"})
    out = gr.read_person(None, "k")
    assert out["hp"] == "1000"
    assert out["level"] == "10"     # extra 补上空字段
    assert out["gold"] == "500"


def test_read_manual_forwards_to_agent(monkeypatch):
    monkeypatch.setattr(gr._monster, "read",
                        lambda image, api_key=None: [{"name": "血蚊"}])
    assert gr.read_manual(None, "k") == [{"name": "血蚊"}]


def test_read_floor_map(monkeypatch):
    empty = np.zeros((0, 0, 3), np.uint8)
    assert gr.read_floor_map(empty, "k") == {"mons": [], "items": [],
                                             "grid": {}}
    monkeypatch.setattr(gr._map, "read",
                        lambda image, api_key=None, known=None, with_items=None,
                        with_monsters=None, with_grid=None:
                        {"mons": [{"name": "血蚊"}], "items": [],
                         "grid": {"cells": []}})
    img = np.zeros((10, 10, 3), np.uint8)
    out = gr.read_floor_map(img, "k")
    assert out["mons"] == [{"name": "血蚊"}]


def test_read_floor_monsters(monkeypatch):
    empty = np.zeros((0, 0, 3), np.uint8)
    assert gr.read_floor_monsters(empty, "k") == []
    monkeypatch.setattr(gr._map, "monsters",
                        lambda image, api_key=None, known=None:
                        [{"name": "血蚊"}])
    img = np.zeros((10, 10, 3), np.uint8)
    assert gr.read_floor_monsters(img, "k") == [{"name": "血蚊"}]


def test_parse_item_schema_gem():
    text = '{"红":[3,2],"蓝":[1,5],"绿":[0,0]}'
    out = gr._parse_item_schema(text, "宝石", "宝石",
                                gem_attrs={"红": "攻击", "蓝": "防御"})
    assert out == [
        {"name": "红宝石", "effect": "攻击+2", "count": 3, "icon": ""},
        {"name": "蓝宝石", "effect": "防御+5", "count": 1, "icon": ""},
    ]


def test_parse_item_schema_gem_no_number():
    text = '{"红":[3]}'
    out = gr._parse_item_schema(text, "宝石", "宝石",
                                gem_attrs={"红": "攻击"})
    assert out[0]["effect"] == "攻击"


def test_parse_item_schema_potion():
    text = '{"红":[2,150]}'
    out = gr._parse_item_schema(text, "药水瓶", "血瓶", gem_attrs={})
    assert out == [{"name": "红血瓶", "effect": "回复150", "count": 2,
                    "icon": ""}]


def test_read_gem_attributes_caches(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(gr, "_GEM_ATTRS", {})
    monkeypatch.setattr(gr, "_ask_model",
                        lambda p, image, api_key=None, max_tokens=None:
                        '{"红":"攻击","蓝":"防御"}')
    out = gr.read_gem_attributes("k", None)
    assert out == {"红": "攻击", "蓝": "防御"}
    # 第二次走缓存，不再调模型
    monkeypatch.setattr(gr, "_ask_model",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("有缓存不该再问")))
    assert gr.read_gem_attributes("k", None) == {"红": "攻击", "蓝": "防御"}


def test_read_items_merges_both_kinds(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(gr, "_GEM_ATTRS", {})

    def fake_model(prompt, image, api_key=None, max_tokens=None):
        if "药水瓶" in prompt:
            return '{"红":[2,150],"蓝":[0,0]}'
        return '{"红":[3,2],"蓝":[1,5]}'

    monkeypatch.setattr(gr, "_ask_model", fake_model)
    monkeypatch.setattr(gr, "read_gem_attributes",
                        lambda api_key=None, image=None:
                        {"红": "攻击", "蓝": "防御"})
    img = np.zeros((10, 10, 3), np.uint8)
    items = gr.read_items(img, "k")
    names = [i["name"] for i in items]
    assert "红血瓶" in names
    assert "红宝石" in names
    assert "蓝宝石" in names


def test_map_snapshot(monkeypatch):
    monkeypatch.setattr(gr.tower_mod, "resolve",
                        lambda tower, image: (None, (2, 3, 4, 5), "cropped"))
    monkeypatch.setattr(gr.R, "crop", lambda img, rect: "CROP")
    img = np.zeros((10, 10, 3), np.uint8)
    assert gr.map_snapshot(object(), img) == "CROP"
    assert gr.map_snapshot(object(), None) is None


def test_map_snapshot_error_returns_none(monkeypatch):
    monkeypatch.setattr(gr.tower_mod, "resolve",
                        lambda tower, image: (_ for _ in ()).throw(
                            Exception("boom")))
    img = np.zeros((10, 10, 3), np.uint8)
    assert gr.map_snapshot(object(), img) is None


def test_iteminfo_icon(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "gem_red")
    assert gr.iteminfo_icon("红宝石") == "gem_red"


# ---- read()：抓图 → 判类型 → 按类型读（并行两问 + 地图会话）----

class _Tower:
    process = "chrome.exe"
    name = "h5mota 魔塔"


def _stubs(monkeypatch, **overrides):
    """把 read() 里所有会碰外部的东西都换掉，只留编排是真的。"""
    import chaita.game.winutil as wu
    monkeypatch.setattr(wu, "window_title", lambda process: "某塔 - 浏览器")
    monkeypatch.setattr(wu, "clean_title", lambda title: "某塔")
    monkeypatch.setattr(gr, "map_snapshot", lambda tower, image: "SNAP")
    monkeypatch.setattr(gr, "iteminfo_icon", lambda name: "icon_" + name)
    monkeypatch.setattr(gr, "grab_window", lambda process: "GRABBED")
    monkeypatch.setattr(gr, "classify", lambda image, api_key=None: "map")
    monkeypatch.setattr(gr, "read_status",
                        lambda image, api_key=None: {"hp": "1000"})
    monkeypatch.setattr(gr, "read_status_extra",
                        lambda image, api_key=None: {"level": "11",
                                                     "gold": "5"})
    monkeypatch.setattr(gr._map, "read",
                        lambda image, api_key=None, known=None: {
                            "floor": "3层", "grid": {"cells": []},
                            "mons": [{"name": "血蚊", "count": 2}],
                            "items": [{"name": "红宝石", "count": 1}]})
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    for name, value in overrides.items():
        target = gr if hasattr(gr, name) else None
        if target is not None:
            monkeypatch.setattr(gr, name, value)
        else:
            monkeypatch.setattr(gr._map, name, value)


def test_read_raises_without_window(monkeypatch):
    import pytest
    _stubs(monkeypatch)
    monkeypatch.setattr(gr, "grab_window", lambda process: None)
    with pytest.raises(RuntimeError):
        gr.read(_Tower(), api_key="k")


def test_read_grabs_when_image_missing(monkeypatch):
    _stubs(monkeypatch)
    grabbed = []
    monkeypatch.setattr(gr, "grab_window",
                        lambda process: grabbed.append(process) or "IMG")

    result = gr.read(_Tower(), api_key="k")

    assert grabbed == ["chrome.exe"]
    assert result.kind == "status"
    assert result.map == "SNAP"


def test_read_manual_screen_only_reads_manual(monkeypatch):
    _stubs(monkeypatch)
    monkeypatch.setattr(gr, "classify", lambda image, api_key=None: "manual")
    monkeypatch.setattr(gr, "read_manual",
                        lambda image, api_key=None: [{"name": "血蚊"}])
    monkeypatch.setattr(gr._map, "read",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("手册页不该去读地图")))

    result = gr.read(_Tower(), api_key="k", image="IMG")

    assert result.kind == "monsters"
    assert result.map is None                 # 手册页不建地图
    assert result.monsters == [{"name": "血蚊"}]
    assert result.status == {}


def test_read_map_merges_status_extra_and_floor(monkeypatch):
    _stubs(monkeypatch)
    result = gr.read(_Tower(), api_key="k", image="IMG")

    # 状态面板：hp 来自主问，level/gold 来自附加那问
    assert result.status["hp"] == "1000"
    assert result.status["level"] == "11"
    assert result.status["gold"] == "5"
    # 层号来自地图会话（状态那问没给）
    assert result.status["floor"] == "3层"
    assert result.name == "某塔"              # 窗口标题清洗过的塔名
    assert result.monsters == [{"name": "血蚊", "count": 2}]
    assert result.items == [{"name": "红宝石", "count": 1,
                             "icon": "icon_红宝石"}]
    assert result.grid == {"cells": []}


def test_read_uses_caller_screen_without_classifying(monkeypatch):
    _stubs(monkeypatch)
    monkeypatch.setattr(gr, "classify",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("调用方判过了就别再判")))

    result = gr.read(_Tower(), api_key="k", image="IMG", screen="map")

    assert result.kind == "status"


def test_read_survives_status_thread_failure(monkeypatch):
    _stubs(monkeypatch)
    monkeypatch.setattr(gr, "read_status",
                        lambda image, api_key=None: (_ for _ in ()).throw(
                            RuntimeError("状态那问挂了")))

    result = gr.read(_Tower(), api_key="k", image="IMG")

    # 状态那问挂了不能把整次读取带崩：层号还是从地图会话拿到
    assert result.status.get("hp") is None
    assert result.status["floor"] == "3层"


def test_read_calls_on_floor_and_swallows_errors(monkeypatch):
    _stubs(monkeypatch)
    seen = []
    gr.read(_Tower(), api_key="k", image="IMG",
            on_floor=lambda floor, image: seen.append((floor, image)))
    assert seen == [("3层", "SNAP")]

    _stubs(monkeypatch)
    result = gr.read(_Tower(), api_key="k", image="IMG",
                     on_floor=lambda floor, image: (_ for _ in ()).throw(
                         RuntimeError("回调炸了")))
    assert result.kind == "status"            # 回调炸了也照样返回结果
