"""会话/窗口状态读写单元测试（`chaita/ui/toolkit/state.py`）。

真值来自规则：空记录不落盘、坏 JSON 当空、file:// 的图没了就清 url、几何按屏夹住。
文件 I/O 用 fake 替掉。
"""

import json

import chaita.ui.toolkit.state as st


class _F:
    def __init__(self, sink=None):
        self.sink = sink if sink is not None else []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def write(self, s):
        self.sink.append(s)


class _Area:
    def __init__(self, x, y, w, h):
        self._ = (x, y, w, h)

    def x(self):
        return self._[0]

    def y(self):
        return self._[1]

    def width(self):
        return self._[2]

    def height(self):
        return self._[3]


def test_url_missing_only_checks_file_url(monkeypatch):
    monkeypatch.setattr(st.os.path, "exists", lambda p: False)
    assert st._url_missing("file:///C:/gone.png") is True
    assert st._url_missing("potion_red") is False
    assert st._url_missing("") is False


def test_session_hint():
    assert st._session_hint({}) == ""
    assert st._session_hint({"floors": [], "monsters": []}) == ""
    assert st._session_hint({"floors": [1, 2]}) == "2 层"
    assert st._session_hint({"monsters": [1]}) == "1 只怪"
    assert st._session_hint({"floors": [1], "monsters": [1, 2],
                             "saved_at": "12:00"}) == "12:00 · 1 层 / 2 只怪"


def test_ui_state_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("CHAITA_NO_UI_STATE", raising=False)
    assert st._ui_state_enabled() is True
    monkeypatch.setenv("CHAITA_NO_UI_STATE", "1")
    assert st._ui_state_enabled() is False


def test_save_session_skips_when_empty(monkeypatch):
    touched = []
    monkeypatch.setattr(st.os, "makedirs",
                        lambda *a, **k: touched.append("makedirs"))
    monkeypatch.setattr(st.os, "replace",
                        lambda *a, **k: touched.append("replace"))
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: touched.append("open") or _F())

    st._save_session([], [])

    assert touched == []                   # 空记录：不建目录、不写文件、不替换


def test_save_session_writes_json(monkeypatch):
    sink = []
    monkeypatch.setattr(st.os.path, "dirname", lambda p: "")
    monkeypatch.setattr(st.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(st.os, "replace", lambda *a, **k: None)
    monkeypatch.setattr("builtins.open", lambda *a, **k: _F(sink))
    st._save_session([{"name": "血蚊"}], [{"floor": "1"}])
    data = json.loads("".join(sink))
    assert data["monsters"] == [{"name": "血蚊"}]
    assert data["floors"] == [{"floor": "1"}]
    assert "saved_at" in data


def test_load_session_bad_json_is_empty(monkeypatch):
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    assert st._load_session() == {}


def test_load_session_cleans_missing_floor_url(monkeypatch):
    import io
    payload = json.dumps({"floors": [{"floor": "1",
                                      "url": "file:///C:/gone.png"}],
                          "monsters": [{"name": "血蚊"}]}, ensure_ascii=False)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO(payload))
    monkeypatch.setattr(st.os.path, "exists", lambda p: False)
    out = st._load_session()
    assert out["floors"][0]["url"] == ""


def test_geometry_from_state_normal(monkeypatch):
    area = _Area(0, 0, 1920, 1040)
    got = st._geometry_from_state({"x": 100, "y": 200, "width": 400,
                                   "height": 800}, area)
    assert got == (100, 200, 400, 800)


def test_geometry_from_state_clamps_size(monkeypatch):
    area = _Area(0, 0, 1920, 1040)
    got = st._geometry_from_state({"x": 100, "y": 200, "width": 10000,
                                   "height": 50}, area)
    assert got == (100, 200, 900, 120)


def test_geometry_from_state_invalid(monkeypatch):
    area = _Area(0, 0, 1920, 1040)
    assert st._geometry_from_state({}, area) is None
    assert st._geometry_from_state({"x": "abc", "y": 0}, area) is None
    assert st._geometry_from_state(None, area) is None


class _Screen:
    def availableGeometry(self):
        return _Area(0, 0, 1920, 1040)


class _Win:
    def __init__(self):
        self.props = {"width": 340, "height": 700}

    def property(self, key):
        return self.props.get(key, 0)

    def setProperty(self, key, value):
        self.props[key] = value


def test_apply_ui_state_restores_position(monkeypatch):
    monkeypatch.setattr(st, "_load_ui_state",
                        lambda: {"x": 100, "y": 200})
    monkeypatch.setattr(st.QGuiApplication, "primaryScreen",
                        lambda: _Screen())
    w = _Win()
    assert st._apply_ui_state(w) is True
    assert w.props["x"] == 100
    assert w.props["y"] == 200


def test_apply_ui_state_no_screen(monkeypatch):
    monkeypatch.setattr(st.QGuiApplication, "primaryScreen", lambda: None)
    assert st._apply_ui_state(object()) is False


def test_place_right(monkeypatch):
    monkeypatch.setattr(st.QGuiApplication, "primaryScreen",
                        lambda: _Screen())
    w = _Win()
    st._place_right(w)
    assert w.props["x"] == 1920 - 340 - st.MARGIN
    assert w.props["y"] == st.MARGIN


# ---- 读回来的形状不对要当空 ----

def _payload(monkeypatch, data):
    import io
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO(json.dumps(data)))


def test_load_session_rejects_wrong_shapes(monkeypatch):
    _payload(monkeypatch, ["不是 dict"])
    assert st._load_session() == {}

    _payload(monkeypatch, {"monsters": "x", "floors": []})
    assert st._load_session() == {}

    _payload(monkeypatch, {"monsters": [], "floors": []})
    assert st._load_session() == {}


def test_load_session_skips_bad_floor_and_monster_entries(monkeypatch):
    monkeypatch.setattr(st, "_fix_monster_icon", lambda one: dict(one))
    _payload(monkeypatch, {"floors": ["坏的", {"floor": "1"}],
                           "monsters": ["坏的", {"name": "血蚊"}]})

    out = st._load_session()

    assert out["floors"] == [{"floor": "1"}]
    assert out["monsters"] == [{"name": "血蚊"}]


# ---- 怪物图标：素材改名之后老记录要能跟上 ----

def test_fix_monster_icon_prefers_stable_icon_id(monkeypatch):
    import chaita.library as lib
    seen = []
    monkeypatch.setattr(lib, "url_of",
                        lambda icon_id: seen.append(icon_id) or "NEW.png")

    row = st._fix_monster_icon({"icon_id": "monster/guard_e380",
                                "icon": "old.png"})

    assert row["icon"] == "NEW.png"
    assert seen == ["monster/guard_e380"]


def test_fix_monster_icon_looks_up_by_old_file_name(monkeypatch):
    import chaita.library as lib
    monkeypatch.setattr(st.os.path, "exists", lambda p: False)
    asked = []
    monkeypatch.setattr(lib, "id_of_file",
                        lambda stem: asked.append(stem) or "monster/guard")
    monkeypatch.setattr(lib, "url_of", lambda icon_id: "FOUND.png")

    row = st._fix_monster_icon({"icon": "file:///C:/old/xinxin2_E380.png"})

    assert asked == ["xinxin2_E380"]
    assert row["icon"] == "FOUND.png"
    assert row["icon_id"] == "monster/guard"


def test_fix_monster_icon_clears_when_really_gone(monkeypatch):
    import chaita.library as lib
    monkeypatch.setattr(st.os.path, "exists", lambda p: False)
    monkeypatch.setattr(lib, "id_of_file", lambda stem: "")
    monkeypatch.setattr(lib, "url_of", lambda icon_id: "不该被用到")

    row = st._fix_monster_icon({"icon": "file:///C:/old/gone.png"})

    assert row["icon"] == ""
    assert row["icon_id"] == ""


def test_fix_item_icons_migrates_old_game_prefix():
    """老存档里的资源图标名（带别人游戏的前缀）要跟到现在的新名字。"""
    entry = {"items": [{"name": "铁剑", "icon": "xinxin2_sword1"},
                       {"name": "铁盾", "icon": "xinxin_shield1"},
                       {"name": "红宝石", "icon": "gem_red"},
                       {"name": "没图标", "icon": ""}],
             "routes": [{"cells": [{"kind": "item", "name": "铁剑",
                                    "icon": "xinxin2_sword1"},
                                   {"kind": "monster", "name": "史莱姆"}]}]}

    row = st._fix_item_icons(entry)

    assert [one["icon"] for one in row["items"]] == [
        "sword", "shield", "gem_red", ""]
    assert row["routes"][0]["cells"][0]["icon"] == "sword"
    assert "icon" not in row["routes"][0]["cells"][1]


def test_fix_item_icons_leaves_entries_without_items_alone():
    assert st._fix_item_icons({"floor": "1层"}) == {"floor": "1层"}


def test_fix_monster_icon_keeps_texture_name(monkeypatch):
    """不是文件 URL 的图标（贴图名）不动它。"""
    row = st._fix_monster_icon({"icon": "potion_red"})
    assert row["icon"] == "potion_red"


# ---- 窗口状态文件 ----

def test_save_ui_state_writes_indented_json(monkeypatch):
    sink = []
    monkeypatch.delenv("CHAITA_NO_UI_STATE", raising=False)
    monkeypatch.setattr(st.os.path, "dirname", lambda p: "")
    monkeypatch.setattr(st.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(st.os, "replace", lambda *a, **k: None)
    monkeypatch.setattr("builtins.open", lambda *a, **k: _F(sink))

    st._save_ui_state({"x": 1, "y": 2})

    assert json.loads("".join(sink)) == {"x": 1, "y": 2}


def test_ui_state_files_respect_the_env_switch(monkeypatch):
    monkeypatch.setenv("CHAITA_NO_UI_STATE", "1")
    monkeypatch.setattr(st.os, "replace",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("开关关掉就不该落盘")))
    st._save_ui_state({"x": 1})            # 不写
    assert st._load_ui_state() == {}       # 也不读


def test_load_ui_state_bad_json_is_empty(monkeypatch):
    monkeypatch.delenv("CHAITA_NO_UI_STATE", raising=False)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    assert st._load_ui_state() == {}


def test_load_ui_state_non_dict_is_empty(monkeypatch):
    monkeypatch.delenv("CHAITA_NO_UI_STATE", raising=False)
    _payload(monkeypatch, ["不是 dict"])
    assert st._load_ui_state() == {}


# ---- 几何：位置也要夹 ----

def test_geometry_clamps_position_into_screen():
    area = _Area(0, 0, 1920, 1040)
    x, y, _w, _h = st._geometry_from_state({"x": 99999, "y": 99999}, area)
    assert x == 1920 - 60                  # 至少留 60px 在屏幕里
    assert y == 1040 - 40                  # 纵向留 40px


def test_geometry_bad_size_is_none():
    area = _Area(0, 0, 1920, 1040)
    assert st._geometry_from_state({"x": 1, "y": 1, "width": "abc"}, area) is None
    assert st._geometry_from_state({"x": 1, "y": 1, "height": "abc"}, area) is None


def test_apply_ui_state_bad_geometry_falls_back(monkeypatch):
    monkeypatch.setattr(st, "_load_ui_state", lambda: {})
    monkeypatch.setattr(st.QGuiApplication, "primaryScreen",
                        lambda: _Screen())
    assert st._apply_ui_state(_Win()) is False


def test_place_right_clamps_too_tall_window(monkeypatch):
    monkeypatch.setattr(st.QGuiApplication, "primaryScreen",
                        lambda: _Screen())
    w = _Win()
    w.props["height"] = 5000

    st._place_right(w)

    assert w.props["height"] == 1040 - 2 * st.MARGIN   # 压到放得下
    assert w.props["y"] == st.MARGIN


def test_place_right_without_screen_does_nothing(monkeypatch):
    monkeypatch.setattr(st.QGuiApplication, "primaryScreen", lambda: None)
    w = _Win()
    st._place_right(w)
    assert "x" not in w.props              # 没屏幕就别乱摆
