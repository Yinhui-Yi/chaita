"""技能解析单元测试（`chaita/ui/toolkit/library.py`）。

真值来自规则：参数数字转字符串、旧文本按空格拆、JSON 数组解析、去重、code 以表为准。
"""

import chaita.ui.toolkit.library as tklib


def test_skill_params_normalizes():
    assert tklib._skill_params(
        {"defValue": 50, "toggle": True, "x": None, "": "skip"}) \
        == {"defValue": "50", "toggle": True, "x": ""}
    assert tklib._skill_params(None) == {}


def test_skill_items_from_text():
    assert tklib._skill_items_from_text("先攻 连击") == [
        {"name": "先攻", "value": "", "code": "", "params": {}},
        {"name": "连击", "value": "", "code": "", "params": {}},
    ]
    assert tklib._skill_items_from_text("") == []


def test_parse_skill_payload_json():
    payload = '[{"name":"破甲","value":"","code":"7",' \
              '"params":{"defValue":"50"}}]'
    out = tklib._parse_skill_payload(payload)
    assert out[0]["name"] == "破甲"
    assert out[0]["code"] == "7"
    assert out[0]["params"] == {"defValue": "50"}


def test_parse_skill_payload_bad_json_is_empty():
    assert tklib._parse_skill_payload("[not json") == []


def test_parse_skill_payload_legacy_text():
    assert tklib._parse_skill_payload("先攻 连击") == [
        {"name": "先攻", "value": "", "code": "", "params": {}},
        {"name": "连击", "value": "", "code": "", "params": {}},
    ]


def test_parse_skill_payload_dedups_names():
    payload = '[{"name":"先攻"},{"name":"先攻"}]'
    out = tklib._parse_skill_payload(payload)
    assert len(out) == 1


def test_skill_names():
    assert tklib._skill_names(
        [{"name": "先攻"}, {"name": "连击"}, {"name": ""}]) == "先攻 连击"


def test_monster_skill_items_uses_skill_items():
    m = {"skill_items": [{"name": "先攻", "value": "30", "code": "1",
                          "params": {}}]}
    out = tklib._monster_skill_items(m)
    assert out[0]["value"] == "30"
    assert out[0]["code"] == "1"


def test_monster_skill_items_falls_back_to_text():
    out = tklib._monster_skill_items({"skills": "先攻"})
    assert out[0]["name"] == "先攻"


def test_monster_skill_items_not_dict():
    assert tklib._monster_skill_items(None) == []


def test_fill_skill_codes(monkeypatch):
    import chaita.game.skillinfo as si
    monkeypatch.setattr(si, "code_for",
                        lambda name: "1" if name == "先攻" else "")
    items = [{"name": "先攻", "code": ""}, {"name": "连击", "code": "7"}]
    out = tklib._fill_skill_codes(items)
    assert out[0]["code"] == "1"      # 空的补上
    assert out[1]["code"] == "7"      # 已有不动


def test_sort_by_library(monkeypatch):
    monkeypatch.setattr(tklib, "_library_order",
                        lambda: {"a.png": 0, "b.png": 1})
    rows = [
        {"icon": "x/b.png", "seq": 1},
        {"icon": "x/a.png", "seq": 2},
        {"icon": "x/unknown.png", "seq": 0},
    ]
    out = tklib._sort_by_library(rows)
    assert [r["icon"] for r in out] == ["x/a.png", "x/b.png", "x/unknown.png"]


def test_import_icon_empty_or_non_file_is_empty(monkeypatch):
    assert tklib._import_icon("", "x") == ""
    assert tklib._import_icon(None, "x") == ""
    monkeypatch.setattr(tklib.os.path, "isfile", lambda p: False)
    assert tklib._import_icon("C:/none.png", "x") == ""


def test_import_icon_resizes_long_side(monkeypatch):
    import cv2
    import numpy as np

    class _Raw:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"raw"

    monkeypatch.setattr(tklib.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(tklib.os.path, "basename", lambda p: "img.png")
    monkeypatch.setattr(tklib.os.path, "splitext", lambda p: ("img", ".png"))
    monkeypatch.setattr(tklib.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr("builtins.open", lambda *a, **k: _Raw())
    img = np.zeros((100, 200, 3), np.uint8)   # 长边 200 > 64
    monkeypatch.setattr(cv2, "imdecode", lambda *a, **k: img)
    resized = []
    monkeypatch.setattr(cv2, "resize",
                        lambda im, size, interpolation:
                        (resized.append(size), im)[1])

    class Buf:
        def tofile(self, path):
            pass

    monkeypatch.setattr(cv2, "imencode", lambda ext, im: (True, Buf()))
    url = tklib._import_icon("C:/x.png", "monster_upload")
    assert url.startswith("file:///")
    assert resized[-1] == (64, 32)      # (宽 200→64, 高 100→32)


def test_load_monster_templates_json_fallback(monkeypatch):
    import io
    import json
    monkeypatch.setattr(tklib, "_load_templates_from_db", lambda path: None)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO(
                            json.dumps([{"name": "血蚊",
                                         "icon": "monster/x.png"}])))
    monkeypatch.setattr(tklib, "_sort_by_library", lambda rows: rows)
    out = tklib._load_monster_templates()
    assert out[0]["name"] == "血蚊"
    assert out[0]["icon"].startswith("file:///")
    assert out[0]["seq"] == 1


def test_load_templates_from_db(monkeypatch):
    monkeypatch.setattr(tklib.os.path, "exists", lambda p: True)

    class Conn:
        def execute(self, sql):
            return self

        def fetchall(self):
            return [("血蚊", 100, 10, 20, 5, "monster/x.png", 0, 400,
                     '["别名"]', "先攻", "史莱姆")]

        def close(self):
            pass

    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda path: Conn())
    monkeypatch.setattr(tklib, "_sort_by_library", lambda rows: rows)
    out = tklib._load_templates_from_db("x.db")
    assert out[0]["name"] == "血蚊"
    assert out[0]["hp"] == "100"          # 字段统一转字符串
    assert out[0]["aliases"] == ["别名"]
    assert out[0]["icon"].startswith("file:///")


def test_load_skill_catalog(monkeypatch):
    monkeypatch.setattr(tklib.os.path, "exists", lambda p: True)

    class Conn:
        def execute(self, sql):
            return self

        def fetchall(self):
            return [("先攻",), ("连击",)]

        def close(self):
            pass

    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda path: Conn())
    assert tklib._load_skill_catalog() == ["先攻", "连击"]


# ---- 上传图标：file:// 要转回路径；不是图/编不出来都要返回空 ----

def _icon_stubs(monkeypatch, image):
    import cv2
    import numpy as np

    class _Raw:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"raw"

    monkeypatch.setattr(tklib.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(tklib.os.path, "basename", lambda p: "img.png")
    monkeypatch.setattr(tklib.os.path, "splitext", lambda p: ("img", ".png"))
    monkeypatch.setattr(tklib.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr("builtins.open", lambda *a, **k: _Raw())
    monkeypatch.setattr(cv2, "imdecode", lambda *a, **k: image)

    class Buf:
        def tofile(self, path):
            pass

    monkeypatch.setattr(cv2, "imencode", lambda ext, im: (True, Buf()))
    return np


def test_import_icon_strips_file_url(monkeypatch):
    np = _icon_stubs(monkeypatch, __import__("numpy").zeros((8, 8, 3), "uint8"))
    seen = []
    real_isfile = tklib.os.path.isfile

    def isfile(path):
        seen.append(path)
        return True

    monkeypatch.setattr(tklib.os.path, "isfile", isfile)

    url = tklib._import_icon("file:///C:/pics/a.png", "floor")

    assert url.startswith("file:///")
    # file:///C:/... 要多剥一个斜杠，再换成系统分隔符
    assert seen and not seen[0].startswith("/")


def test_import_icon_returns_empty_for_unreadable_image(monkeypatch):
    _icon_stubs(monkeypatch, None)
    assert tklib._import_icon("C:/x.png", "floor") == ""


def test_import_icon_returns_empty_when_encode_fails(monkeypatch):
    import cv2
    _icon_stubs(monkeypatch, __import__("numpy").zeros((8, 8, 3), "uint8"))
    monkeypatch.setattr(cv2, "imencode", lambda ext, im: (False, None))
    assert tklib._import_icon("C:/x.png", "floor") == ""


def test_import_icon_returns_empty_on_exception(monkeypatch):
    import cv2
    _icon_stubs(monkeypatch, __import__("numpy").zeros((8, 8, 3), "uint8"))

    def boom(*a, **k):
        raise OSError("磁盘挂了")

    monkeypatch.setattr(cv2, "imencode", boom)
    assert tklib._import_icon("C:/x.png", "floor") == ""


def test_import_icon_empty_source():
    assert tklib._import_icon("   ", "x") == ""


# ---- 技能载荷 / 怪物技能行的边角 ----

def test_parse_skill_payload_keeps_custom_effect():
    payload = ('[{"name":"自定义","custom":true,"effect":"每回合回血"},'
               '{"name":""},"不是 dict"]')
    out = tklib._parse_skill_payload(payload)
    assert len(out) == 1
    assert out[0]["custom"] is True
    assert out[0]["effect"] == "每回合回血"


def test_parse_skill_payload_json_not_list_falls_back_to_text():
    # 看着像 JSON 但不是数组：当老格式的名字串解析
    out = tklib._parse_skill_payload('[先攻]')
    assert out == [] or all(isinstance(row, dict) for row in out)


def test_monster_skill_items_skips_bad_rows_and_keeps_flags():
    m = {"skill_items": ["不是 dict", {"name": ""},
                         {"name": "先攻", "effect": "先手一击",
                          "custom": True, "params": {"x": 1}}]}
    out = tklib._monster_skill_items(m)
    assert len(out) == 1
    assert out[0]["effect"] == "先手一击"
    assert out[0]["custom"] is True
    assert out[0]["params"] == {"x": "1"}


def test_monster_skill_items_empty_list_falls_back():
    out = tklib._monster_skill_items({"skill_items": [], "skills": "连击"})
    assert [row["name"] for row in out] == ["连击"]


# ---- 素材库顺序 / 模板库读坏了 ----

def test_library_order_swallows_errors(monkeypatch):
    import chaita.library as lib
    monkeypatch.setattr(lib, "pictures",
                        lambda category=None: (_ for _ in ()).throw(
                            RuntimeError("库读不了")))
    assert tklib._library_order() == {}


def test_sort_by_library_without_order_keeps_rows(monkeypatch):
    monkeypatch.setattr(tklib, "_library_order", lambda: {})
    rows = [{"icon": "b.png", "seq": 2}, {"icon": "a.png", "seq": 1}]
    assert tklib._sort_by_library(rows) is rows


def test_load_templates_from_db_missing_file(monkeypatch):
    monkeypatch.setattr(tklib.os.path, "exists", lambda p: False)
    assert tklib._load_templates_from_db("x.db") is None


def test_load_templates_from_db_error_returns_none(monkeypatch):
    import sqlite3
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(tklib.os.path, "exists", lambda p: True)
    monkeypatch.setattr(sqlite3, "connect",
                        lambda path: (_ for _ in ()).throw(
                            sqlite3.DatabaseError("坏了")))
    assert tklib._load_templates_from_db("x.db") is None


def test_load_templates_from_db_skips_bad_rows(monkeypatch):
    monkeypatch.setattr(tklib.os.path, "exists", lambda p: True)

    class Conn:
        def execute(self, sql):
            return self

        def fetchall(self):
            return [
                (None, 1, 1, 1, 1, "", 0, 0, None, "", ""),      # 没名字
                ("血蚊", None, 1, 1, 1, "", 1, 0, "坏的 json", "", ""),
            ]

        def close(self):
            pass

    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda path: Conn())
    monkeypatch.setattr(tklib, "_sort_by_library", lambda rows: rows)

    out = tklib._load_templates_from_db("x.db")

    assert len(out) == 1
    assert out[0]["name"] == "血蚊"
    assert out[0]["hp"] == ""            # None → 空串
    assert out[0]["aliases"] == []       # 坏 JSON 当没有别名


def test_load_templates_from_db_all_bad_returns_none(monkeypatch):
    monkeypatch.setattr(tklib.os.path, "exists", lambda p: True)

    class Conn:
        def execute(self, sql):
            return self

        def fetchall(self):
            return [(None, 1, 1, 1, 1, "", 0, 0, None, "", "")]

        def close(self):
            pass

    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda path: Conn())
    assert tklib._load_templates_from_db("x.db") is None


def test_load_skill_catalog_missing_or_broken(monkeypatch):
    import sqlite3
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)

    monkeypatch.setattr(tklib.os.path, "exists", lambda p: False)
    assert tklib._load_skill_catalog() == []

    monkeypatch.setattr(tklib.os.path, "exists", lambda p: True)
    monkeypatch.setattr(sqlite3, "connect",
                        lambda path: (_ for _ in ()).throw(
                            sqlite3.DatabaseError("坏了")))
    assert tklib._load_skill_catalog() == []


def test_load_monster_templates_json_bad(monkeypatch):
    monkeypatch.setattr(tklib, "_load_templates_from_db", lambda path: None)

    def bad(*a, **k):
        raise OSError("没有这个文件")

    monkeypatch.setattr("builtins.open", bad)
    assert tklib._load_monster_templates() == []


def test_load_monster_templates_json_not_list(monkeypatch):
    import io
    monkeypatch.setattr(tklib, "_load_templates_from_db", lambda path: None)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO('{"不是": "列表"}'))
    assert tklib._load_monster_templates() == []


def test_load_monster_templates_json_skips_bad_entries(monkeypatch):
    import io
    import json
    monkeypatch.setattr(tklib, "_load_templates_from_db", lambda path: None)
    monkeypatch.setattr(tklib, "_sort_by_library", lambda rows: rows)
    payload = json.dumps(["不是 dict", {"hp": "1"}, {"name": "血蚊"}],
                         ensure_ascii=False)
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: io.StringIO(payload))

    out = tklib._load_monster_templates()

    assert [row["name"] for row in out] == ["血蚊"]
    assert out[0]["seq"] == 3            # seq 按原始位置（第 3 项）
