"""怪物编辑链路集成测试（`chaita/ui/controller/monsters/edit.py`）。

真值从规则手推：加模板按 skills 串拆技能、code 从 skillinfo 表查；删怪要把各层地图一起删。
"""

from .... import helpers


def test_add_monster_tpl_fills_skill_code(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    controller, engine, window = helpers.make_controller()

    controller.addMonsterTpl("血蚊", "1200", "60", "20", "5", "先攻", "")

    m = controller._monsters[0]
    assert m["name"] == "血蚊"
    assert m["hp"] == "1200"
    assert [s["name"] for s in m["skill_items"]] == ["先攻"]
    # 跨模块：_fill_skill_codes → skillinfo.code_for("先攻") → 引擎号 1
    assert m["skill_items"][0]["code"] == "1"


def test_remove_monster_by_name_clears_floors(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    controller, engine, window = helpers.make_controller()
    controller._monsters = [{"name": "血蚊"}, {"name": "铁卫"}]
    controller._map_history = [{"floor": "1",
                                "mons": [{"name": "血蚊", "count": 2},
                                         {"name": "铁卫", "count": 1}]}]

    controller.removeMonsterByName("血蚊")

    assert [m["name"] for m in controller._monsters] == ["铁卫"]
    assert controller._map_history[0]["mons"] == [{"name": "铁卫", "count": 1}]
