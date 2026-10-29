"""怪物增删改排序单元测试（`chaita/ui/controller/monsters/edit.py`）。

真值来自规则：名字空 = 删；金币 None = 别动、"" = 清空；顺序 = 列表顺序本身；
删怪要把各层地图里同一只一起删掉（不然那层又会把它顶出来）。
"""

from unittest.mock import Mock

from chaita.ui.controller.monsters.edit import EditMixin


class FakeEdit(EditMixin):
    def __init__(self, monsters=None, history=None):
        self._monsters = [dict(m) for m in (monsters or [])]
        self._map_history = history or []
        self.monstersChanged = Mock()
        self.mapHistoryChanged = Mock()


def test_add_monster_tpl_builds_item():
    c = FakeEdit()
    c.addMonsterTpl("血蚊", "1200", "60", "20", "5", "先攻", "mon.png")
    item = c._monsters[0]
    assert item["name"] == "血蚊"
    assert item["hp"] == "1200"
    assert item["atk"] == "60"
    assert item["def"] == "20"
    assert item["exp"] == "5"
    assert item["gold"] == ""          # 金币只有玩家知道，默认留空
    assert item["skills"] == "先攻"
    # 技能拆成一行一个（数值挂在 skill_items 上）
    assert [s["name"] for s in item["skill_items"]] == ["先攻"]
    assert c.monstersChanged.emit.called


def test_add_monster_tpl_blank_name_gets_placeholder():
    c = FakeEdit()
    c.addMonsterTpl("  ", "", "", "", "", "", "")
    assert c._monsters[0]["name"] == "新怪物"


def test_save_monster_empty_name_deletes():
    c = FakeEdit([{"name": "血蚊", "hp": "1200"}])
    c.saveMonster(0, "", "", "", "", "", "", "")
    assert c._monsters == []


def test_save_monster_full_updates_gold_clear_and_keep():
    c = FakeEdit([{"name": "血蚊", "hp": "1200", "gold": "8"}])
    # 传 ""：用户把金币栏清空，真的要清掉
    c.saveMonsterFull(0, "血蚊", "1300", "60", "20", "5", "先攻", "", "", gold="")
    assert c._monsters[0]["hp"] == "1300"
    assert c._monsters[0]["gold"] == ""
    # 传 None：调用方不知道有这一栏，原来的值别动
    c.saveMonsterFull(0, "血蚊", "1400", "60", "20", "5", "先攻", "", "", gold=None)
    assert c._monsters[0]["gold"] == ""


def test_save_monster_full_gold_none_keeps_old():
    c = FakeEdit([{"name": "血蚊", "hp": "1200", "gold": "8"}])
    c.saveMonsterFull(0, "血蚊", "1300", "60", "20", "5", "先攻", "", "")
    assert c._monsters[0]["gold"] == "8"


def test_move_monster_reorders():
    c = FakeEdit([{"name": "a"}, {"name": "b"}, {"name": "c"}])
    c.moveMonster(2, 0)
    assert [m["name"] for m in c._monsters] == ["c", "a", "b"]
    # 越界 / 原地不动 = 没发生
    c.moveMonster(9, 0)
    c.moveMonster(1, 1)
    assert [m["name"] for m in c._monsters] == ["c", "a", "b"]


def test_remove_monster_by_name_clears_floors():
    c = FakeEdit(
        [{"name": "血蚊"}, {"name": "铁卫"}],
        history=[{"floor": "1层", "mons": [{"name": "血蚊", "count": 2},
                                           {"name": "铁卫", "count": 1}]}])
    c.removeMonsterByName("血蚊")
    assert [m["name"] for m in c._monsters] == ["铁卫"]
    assert c._map_history[0]["mons"] == [{"name": "铁卫", "count": 1}]
    assert c.mapHistoryChanged.emit.called


def test_set_monster_skill_value_sets_and_appends():
    c = FakeEdit([{"name": "血蚊", "skills": "先攻",
                   "skill_items": [{"name": "先攻", "value": "", "code": "1",
                                    "params": {}}]}])
    c.setMonsterSkillValue(0, "先攻", "30")
    assert c._monsters[0]["skill_items"][0]["value"] == "30"
    # 老数据里没有这一条：补出来，别丢用户填的值
    c.setMonsterSkillValue(0, "连击", "2")
    names = [s["name"] for s in c._monsters[0]["skill_items"]]
    assert names == ["先攻", "连击"]
    assert c._monsters[0]["skill_items"][1]["value"] == "2"


def test_remove_monster_by_index():
    c = FakeEdit([{"name": "血蚊"}, {"name": "铁卫"}])
    c.removeMonster(0)
    assert [m["name"] for m in c._monsters] == ["铁卫"]


def test_save_monster_updates_fields():
    c = FakeEdit([{"name": "血蚊", "hp": "1200"}])
    c.saveMonster(0, "铁卫", "900", "40", "10", "5", "先攻", "")
    m = c._monsters[0]
    assert m["name"] == "铁卫"
    assert m["hp"] == "900"
    assert m["atk"] == "40"
    assert m["skills"] == "先攻"
