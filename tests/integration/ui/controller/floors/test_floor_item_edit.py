"""本层资源编辑链路集成测试（`chaita/ui/controller/floors/items.py`）。

真值从规则手推：图标/默认效果按名字从道具表查（iteminfo 真跑）、数量取数字、换种类一起换。
"""

from .... import helpers


def test_add_item_full_fills_icon_and_effect(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{"floor": "1", "items": []}]

    idx = controller.addItemFull("1", "红宝石", "", "3", "")

    item = controller._map_history[0]["items"][idx]
    assert item["name"] == "红宝石"
    assert item["icon"] == "gem_red"      # iteminfo.icon_for 真跑
    assert item["count"] == 3
    assert item["effect"]                 # 默认效果从道具表查，非空


def test_set_item_kind_replaces_icon_and_effect(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{"floor": "1",
                                "items": [{"name": "红宝石", "icon": "gem_red",
                                           "effect": "攻击力 +1", "count": 2}]}]

    controller.setItemKind("1", 0, "血瓶", "potion_red", "")

    item = controller._map_history[0]["items"][0]
    assert item["name"] == "血瓶"
    assert item["icon"] == "potion_red"
    assert item["effect"]                 # 血瓶默认效果（体力 +N）
    assert item["count"] == 2             # 数量不动


def test_add_item_full_keeps_passed_effect(monkeypatch):
    # 传进去的效果不能被道具表默认值盖掉：两个血瓶 150 / 300 要能各是各的
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{"floor": "1", "items": []}]

    idx = controller.addItemFull("1", "血瓶", "体力 +300", "1", "")

    item = controller._map_history[0]["items"][idx]
    assert item["effect"] == "体力 +300"
