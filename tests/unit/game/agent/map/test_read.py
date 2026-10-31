"""map read 的清洗函数单元测试（`chaita/game/agent/map/read.py`）。

真值来自规则：同名合并、数量上限、坐标 1 基转 0 基、13×13、只留怪/宝石/血瓶。
"""

from chaita.game.agent.map import read as map_read


def test_clean_merges_same_name():
    assert map_read.clean([{"name": "红头怪", "count": 3},
                           {"name": "红头怪", "count": 2}]) \
        == [{"name": "红头怪", "count": 5}]


def test_clean_drops_empty_and_non_positive():
    assert map_read.clean([{"name": "", "count": 1},
                           {"name": "怪", "count": 0}]) == []


def test_clean_drops_absurd_count():
    # MAX_COUNT = 60，超过就丢掉（把血量/效果当数量的）
    assert map_read.clean([{"name": "超多", "count": 61}]) == []


def test_clean_cells_shifts_to_zero_based_and_filters():
    cells = map_read.clean_cells([
        {"row": 2, "col": 3, "kind": "monster", "name": "红头怪"},
        {"row": 5, "col": 7, "kind": "item", "name": "红宝石"},
        {"row": 6, "col": 2, "kind": "item", "name": "红血瓶"},
        {"row": 2, "col": 4, "kind": "door", "name": "黄门"},      # 门不记
        {"row": 14, "col": 3, "kind": "monster", "name": "越界"},  # 越界丢
        {"row": 9, "col": 9, "kind": "monster", "name": ""},        # 空名丢
    ])
    assert cells == [
        {"row": 1, "col": 2, "kind": "monster", "name": "红头怪"},
        {"row": 4, "col": 6, "kind": "item", "name": "红宝石"},
        {"row": 5, "col": 1, "kind": "item", "name": "红血瓶"},
    ]


def test_clean_cells_drops_duplicate():
    cells = map_read.clean_cells([
        {"row": 3, "col": 3, "kind": "monster", "name": "丙"},
        {"row": 3, "col": 3, "kind": "item", "name": "红宝石"},
    ])
    assert cells == [{"row": 2, "col": 2, "kind": "monster", "name": "丙"}]


def test_clean_cells_keeps_every_stair_of_the_floor():
    """一层可以有好几个楼梯（用户："谁告诉你一层只有一个上楼或下楼的？"）。

    模型报 `stair_up` / `stair_down` 时名字可以空着，补一个统一的名字；
    通到哪一层它看不到，这里也不瞎填。
    """
    cells = map_read.clean_cells([
        {"row": 1, "col": 12, "kind": "stair_up"},
        {"row": 4, "col": 5, "kind": "stair_up", "name": "上楼梯"},
        {"row": 12, "col": 1, "kind": "stair_down", "name": "下楼梯"},
        {"row": 13, "col": 13, "kind": "stair_up"},
    ])
    assert cells == [
        {"row": 0, "col": 11, "kind": "stair_up", "name": "上楼梯"},
        {"row": 3, "col": 4, "kind": "stair_up", "name": "上楼梯"},
        {"row": 11, "col": 0, "kind": "stair_down", "name": "下楼梯"},
        {"row": 12, "col": 12, "kind": "stair_up", "name": "上楼梯"},
    ]


def test_clean_layout():
    assert map_read.clean_layout({}) == {}
    assert map_read.clean_layout({"cells": []}) == {}
    assert map_read.clean_layout(
        {"cells": [{"row": 1, "col": 1, "kind": "monster", "name": "甲"}]}) \
        == {"cells": [{"row": 0, "col": 0, "kind": "monster", "name": "甲"}]}


# ---- 单问：stub core.ask_json，只测"怎么取字段、怎么洗" ----


def test_floor(monkeypatch):
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda session, q, image=None, label=None:
                        {"floor": "地下30"})
    assert map_read.floor(object(), None) == "地下30"


def test_monsters_of(monkeypatch):
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda *a, **k: {"monsters": [{"name": "血蚊",
                                                       "count": 2}]})
    assert map_read.monsters_of(object(), None, None) \
        == [{"name": "血蚊", "count": 2}]


def test_monsters_of_injects_known_names(monkeypatch):
    got = {}
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda session, q, image=None, label=None:
                        (got.update({"q": q}), {"monsters": []})[1])
    map_read.monsters_of(object(), ["红色史莱姆"], None)
    assert "红色史莱姆" in got["q"]     # 候选名写进提示词


def test_items_of(monkeypatch):
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda *a, **k: {"items": [{"name": "红宝石",
                                                    "count": 3}]})
    assert map_read.items_of(object()) == [{"name": "红宝石", "count": 3}]


def test_layout_of(monkeypatch):
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda *a, **k: {"cells": [{"row": 1, "col": 1,
                                                    "kind": "monster",
                                                    "name": "甲"}]})
    assert map_read.layout_of(object()) \
        == {"cells": [{"row": 0, "col": 0, "kind": "monster", "name": "甲"}]}


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_ask(by_label):
    def ask(session, question, image=None, label=None):
        return by_label.get(label, {})
    return ask


def test_read_orchestration(monkeypatch):
    import numpy as np
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(map_read, "_open",
                        lambda image, api_key: _FakeSession())
    monkeypatch.setattr(map_read.core, "ask_json", _fake_ask({
        "map_floor": {"floor": "地下30"},
        "map_mons": {"monsters": [{"name": "血蚊", "count": 2}]},
        "map_items": {"items": [{"name": "红宝石", "count": 1}]},
        "map_grid": {"cells": [{"row": 1, "col": 1, "kind": "monster",
                                "name": "甲"}]},
    }))
    img = np.zeros((10, 10, 3), np.uint8)
    out = map_read.read(img, "k")
    assert out["floor"] == "地下30"
    assert out["mons"] == [{"name": "血蚊", "count": 2}]
    assert out["items"] == [{"name": "红宝石", "count": 1}]
    assert out["grid"] == {"cells": [{"row": 0, "col": 0,
                                      "kind": "monster", "name": "甲"}]}


def test_read_empty_image_returns_default():
    assert map_read.read(None, "k") == {"floor": "", "mons": [], "items": [],
                                        "grid": {}}


def test_monsters_orchestration(monkeypatch):
    import numpy as np
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(map_read, "_open",
                        lambda image, api_key: _FakeSession())
    monkeypatch.setattr(map_read, "monsters_of",
                        lambda session, known=None, image=None:
                        [{"name": "血蚊"}])
    img = np.zeros((10, 10, 3), np.uint8)
    assert map_read.monsters(img, "k") == [{"name": "血蚊"}]
    assert map_read.monsters(None, "k") == []


def test_classify_map_read(monkeypatch):
    import numpy as np
    monkeypatch.setattr(map_read.core, "run",
                        lambda task, msg, image=None, api_key=None: "manual")
    img = np.zeros((10, 10, 3), np.uint8)
    assert map_read.classify(img, "k") == "manual"
    assert map_read.classify(None, "k") == ""
    monkeypatch.setattr(map_read.core, "run",
                        lambda *a, **k: "garbage")
    assert map_read.classify(img, "k") == ""
