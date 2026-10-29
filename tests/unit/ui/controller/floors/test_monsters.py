"""这一层怪的改名/数量/删单元测试（`chaita/ui/controller/floors/monsters.py`）。"""

from unittest.mock import Mock

from chaita.ui.controller.floors.monsters import FloorMonstersMixin


class Fake(FloorMonstersMixin):
    def __init__(self, history):
        self._map_history = history
        self.mapHistoryChanged = Mock()

    def _find_floor(self, floor_text):
        for index, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                return index
        return -1

    def _mark_saved(self, *args, **kwargs):
        pass


def make():
    return Fake([{"floor": "1层", "mons": [{"name": "血蚊", "count": 3}]}])


def test_rename_monster():
    c = make()
    c.saveFloorMonsterField("1层", 0, "name", "铁卫")
    assert c._map_history[0]["mons"][0]["name"] == "铁卫"


def test_set_count():
    c = make()
    c.saveFloorMonsterField("1层", 0, "count", "5")
    assert c._map_history[0]["mons"][0]["count"] == 5
    # 垃圾文本 → 数量清空
    c.saveFloorMonsterField("1层", 0, "count", "abc")
    assert c._map_history[0]["mons"][0]["count"] is None


def test_clear_name_deletes():
    c = make()
    c.saveFloorMonsterField("1层", 0, "name", "")
    assert c._map_history[0]["mons"] == []


def test_out_of_range_is_noop():
    c = make()
    c.saveFloorMonsterField("1层", 9, "name", "x")
    assert c._map_history[0]["mons"][0]["name"] == "血蚊"


def test_unknown_field_is_noop():
    c = make()
    c.saveFloorMonsterField("1层", 0, "hp", "999")
    assert c._map_history[0]["mons"][0] == {"name": "血蚊", "count": 3}


def test_unknown_floor_is_noop():
    c = make()
    assert c.addFloorMonster("没有这层", "铁卫") == -1
    assert c.addFloorMonsterFull("没有这层", "铁卫", "2") == -1
    c.removeFloorMonster("没有这层", 0)
    c.saveFloorMonsterField("没有这层", 0, "name", "x")
    assert len(c._map_history) == 1


def test_add_floor_monster_sorts_and_returns_its_index():
    c = Fake([{"floor": "1层", "mons": [{"name": "血蚊", "count": 1}]}])
    index = c.addFloorMonster("1层", " 铁卫 ")

    names = [m["name"] for m in c._map_history[0]["mons"]]
    assert names == sorted(names)          # 加完按名字重新排
    assert "铁卫" in names                 # 名字已去掉前后空白
    assert names[index] == "铁卫"          # 返回的是**它自己**的位置
    assert c._map_history[0]["mons"][index]["count"] is None


def test_add_floor_monster_defaults_blank_name():
    c = Fake([{"floor": "1层", "mons": []}])
    c.addFloorMonster("1层", "   ")
    assert c._map_history[0]["mons"] == [{"name": "怪物", "count": None}]


def test_add_floor_monster_full_keeps_count_and_icon(monkeypatch):
    import chaita.ui.controller.floors.monsters as monsters_mod
    monkeypatch.setattr(monsters_mod, "_import_icon",
                        lambda path, kind: "icon.png" if path else "")
    c = Fake([{"floor": "1层", "mons": []}])

    index = c.addFloorMonsterFull("1层", "铁卫", "３只", "tmp.png")

    assert index == 0
    assert c._map_history[0]["mons"][0] == {
        "name": "铁卫", "count": 3, "icon": "icon.png"}


def test_add_floor_monster_full_without_icon_or_count(monkeypatch):
    import chaita.ui.controller.floors.monsters as monsters_mod
    monkeypatch.setattr(monsters_mod, "_import_icon", lambda path, kind: "")
    c = Fake([{"floor": "1层", "mons": []}])

    c.addFloorMonsterFull("1层", "铁卫", "abc", "")

    # 没有图就别塞 icon 键；数量不是数字就 None
    assert c._map_history[0]["mons"][0] == {"name": "铁卫", "count": None}


def test_add_floor_monster_full_blank_name_is_rejected(monkeypatch):
    import chaita.ui.controller.floors.monsters as monsters_mod
    monkeypatch.setattr(monsters_mod, "_import_icon", lambda path, kind: "")
    c = Fake([{"floor": "1层", "mons": []}])
    assert c.addFloorMonsterFull("1层", "  ", "1") == -1
    assert c._map_history[0]["mons"] == []


def test_remove_floor_monster_removes_only_that_row():
    c = Fake([{"floor": "1层", "mons": [{"name": "血蚊", "count": 1},
                                       {"name": "铁卫", "count": 1}]}])
    c.removeFloorMonster("1层", 0)
    assert [m["name"] for m in c._map_history[0]["mons"]] == ["铁卫"]


def test_remove_floor_monster_out_of_range_keeps_rows():
    c = Fake([{"floor": "1层", "mons": [{"name": "血蚊", "count": 1}]}])
    c.removeFloorMonster("1层", 5)
    assert len(c._map_history[0]["mons"]) == 1


def test_toggle_done_goes_through_shared_toggle():
    c = Fake([{"floor": "1层", "mons": [{"name": "血蚊", "count": 1}]}])
    seen = []
    c._toggle_done = lambda floor, index, key: seen.append((floor, index, key))

    c.toggleFloorMonsterDone("1层", 0)

    assert seen == [("1层", 0, "mons")]
