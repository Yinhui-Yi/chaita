"""map read 的清洗/汇总函数单元测试（`chaita/game/agent/map/read.py`）。

真值来自规则（用户 2026-10-31）：
  · 只问「每个格子里有什么」，**不问数量** —— 数量 = 这个格子占几格（`tally`）；
  · 格子里钥匙/金币/武器/防具也算 item（"钥匙/武器/防具也需要记"）；
  · 坐标 1 基转 0 基、只留 13×13 以内。
"""

from chaita.game.agent.map import read as map_read


# ---- 数量来自格子（不再问模型）----

def test_tally_counts_cells_and_keeps_first_seen_order():
    cells = [{"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
             {"row": 0, "col": 1, "kind": "monster", "name": "铁卫"},
             {"row": 1, "col": 1, "kind": "monster", "name": "血蚊"},
             {"row": 2, "col": 2, "kind": "item", "name": "红宝石"}]
    assert map_read.tally(cells, "monster") == [
        {"name": "血蚊", "count": 2}, {"name": "铁卫", "count": 1}]
    assert map_read.tally(cells, "item") == [{"name": "红宝石", "count": 1}]


def test_tally_ignores_other_kinds_and_blank_names():
    cells = [{"row": 0, "col": 0, "kind": "stair_up", "name": "上楼梯"},
             {"row": 0, "col": 1, "kind": "monster", "name": ""},
             {"row": 0, "col": 2, "kind": "monster", "name": "甲"}]
    assert map_read.tally(cells, "monster") == [{"name": "甲", "count": 1}]
    assert map_read.tally([], "monster") == []
    assert map_read.tally(None, "monster") == []


# ---- 「每格有什么」的清洗 ----

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


def test_clean_cells_keeps_keys_weapons_and_armor():
    """钥匙/金币/武器/防具都算 item 记下来（用户 2026-10-31："也需要记"）。"""
    cells = map_read.clean_cells([
        {"row": 1, "col": 1, "kind": "item", "name": "黄钥匙"},
        {"row": 1, "col": 2, "kind": "item", "name": "蓝钥匙"},
        {"row": 1, "col": 3, "kind": "item", "name": "金币"},
        {"row": 1, "col": 4, "kind": "item", "name": "铁剑"},
        {"row": 1, "col": 5, "kind": "item", "name": "铁盾"},
    ])
    assert [c["name"] for c in cells] == ["黄钥匙", "蓝钥匙", "金币", "铁剑", "铁盾"]


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


def test_grid_question_asks_for_keys_weapons_and_no_counts():
    """提问词本身也是规则：要钥匙/武器/防具，不要数量。"""
    question = map_read.GRID_QUESTION
    for word in ("钥匙", "金币", "武器", "防具"):
        assert word in question
    assert "不要写数量" in question


# ---- 单问：stub core.ask_json，只测"怎么取字段、怎么洗" ----

def test_floor(monkeypatch):
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda session, q, image=None, label=None:
                        {"floor": "地下30"})
    assert map_read.floor(object(), None) == "地下30"


def test_layout_of(monkeypatch):
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda *a, **k: {"cells": [{"row": 1, "col": 1,
                                                    "kind": "monster",
                                                    "name": "甲"}]})
    assert map_read.layout_of(object()) \
        == {"cells": [{"row": 0, "col": 0, "kind": "monster", "name": "甲"}]}


def test_layout_of_injects_known_names(monkeypatch):
    """手册里的怪名写进提问词（候选写法，不是必须从中挑）。"""
    got = {}
    monkeypatch.setattr(map_read.core, "ask_json",
                        lambda session, q, image=None, label=None:
                        (got.update({"q": q}), {})[1])
    map_read.layout_of(object(), ["红色史莱姆"])
    assert "红色史莱姆" in got["q"]


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
    """一次会话两问：层号 + 每格有什么；清单和数量都从格子数出来。"""
    import numpy as np
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(map_read, "_open",
                        lambda image, api_key: _FakeSession())
    monkeypatch.setattr(map_read.core, "ask_json", _fake_ask({
        "map_floor": {"floor": "地下30"},
        "map_grid": {"cells": [
            {"row": 1, "col": 1, "kind": "monster", "name": "血蚊"},
            {"row": 1, "col": 2, "kind": "monster", "name": "血蚊"},
            {"row": 2, "col": 2, "kind": "item", "name": "红宝石"}]},
    }))
    img = np.zeros((10, 10, 3), np.uint8)
    out = map_read.read(img, "k")
    assert out["floor"] == "地下30"
    assert out["grid"] == {"cells": [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 0, "col": 1, "kind": "monster", "name": "血蚊"},
        {"row": 1, "col": 1, "kind": "item", "name": "红宝石"}]}
    assert out["mons"] == [{"name": "血蚊", "count": 2}]   # 数量 = 两格
    assert out["items"] == [{"name": "红宝石", "count": 1}]


def test_read_asks_only_two_questions(monkeypatch):
    """**不再问数量**：整条路只发"层号"和"每格有什么"两问。"""
    import numpy as np
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(map_read, "_open",
                        lambda image, api_key: _FakeSession())
    labels = []

    def ask(session, question, image=None, label=None):
        labels.append(label)
        return {}

    monkeypatch.setattr(map_read.core, "ask_json", ask)
    map_read.read(np.zeros((10, 10, 3), np.uint8), "k")
    assert labels == ["map_floor", "map_grid"]


def test_read_empty_image_returns_default():
    assert map_read.read(None, "k") == {"floor": "", "grid": {},
                                        "mons": [], "items": []}


def test_monsters_orchestration(monkeypatch):
    """旧入口「只要怪」也按格子数（不再单独问数量）。"""
    import numpy as np
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(map_read, "_open",
                        lambda image, api_key: _FakeSession())
    monkeypatch.setattr(map_read, "layout_of",
                        lambda session, known=None: {"cells": [
                            {"row": 0, "col": 0, "kind": "monster",
                             "name": "血蚊"},
                            {"row": 0, "col": 1, "kind": "monster",
                             "name": "血蚊"}]})
    img = np.zeros((10, 10, 3), np.uint8)
    assert map_read.monsters(img, "k") == [{"name": "血蚊", "count": 2}]
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
