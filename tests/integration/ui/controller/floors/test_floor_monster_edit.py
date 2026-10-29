"""本层怪手动编辑链路集成测试（`chaita/ui/controller/floors/monsters.py`）。

真值从规则手推：加一只按名字排序、数量取数字。
"""

from .... import helpers


def test_add_floor_monster_and_sort(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    controller, engine, window = helpers.make_controller()
    controller._map_history = [{"floor": "1", "mons": [], "items": []}]

    controller.addFloorMonsterFull("1", "铁卫", "3", "")
    index = controller.addFloorMonsterFull("1", "血蚊", "2", "")

    mons = controller._map_history[0]["mons"]
    names = [m["name"] for m in mons]
    assert names == sorted(names)          # 按名字排
    assert mons[index]["name"] == "血蚊"   # 返回的是新加那只的位置
    assert mons[index]["count"] == 2
