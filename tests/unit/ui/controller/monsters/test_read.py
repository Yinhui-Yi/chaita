"""怪物读取列表单元测试（`chaita/ui/controller/monsters/read.py`）。

真值来自规则：技能只统计地图上加过的怪、同名技能一只只算一次、老 skills 串补齐成行。
"""

from chaita.ui.controller.monsters.read import ReadMixin


class FakeRead(ReadMixin):
    def __init__(self, monsters=None, history=None):
        self._monsters = monsters or []
        self._map_history = history or []
        self._monster_templates = []
        self._skill_catalog = ["先攻"]
        self._tower_label = ""


def test_map_monster_names_dedup_in_order():
    c = FakeRead(history=[
        {"mons": [{"name": "血蚊"}, {"name": "铁卫"}]},
        {"mons": [{"name": "血蚊"}, {"name": "史莱姆"}]},
    ])
    assert c._map_monster_names() == ["血蚊", "铁卫", "史莱姆"]


def test_get_monsters_fills_skill_items():
    c = FakeRead(monsters=[{"name": "血蚊", "skills": "先攻"}])
    out = c._get_monsters()
    assert out[0]["name"] == "血蚊"
    assert [s["name"] for s in out[0]["skill_items"]] == ["先攻"]


def test_skill_stats_only_map_monsters():
    c = FakeRead(
        monsters=[
            {"name": "血蚊",
             "skill_items": [{"name": "先攻", "value": "30", "code": "1",
                              "params": {}}]},
            {"name": "铁卫",
             "skill_items": [{"name": "破甲", "value": "50", "code": "7",
                              "params": {}}]},
        ],
        history=[{"mons": [{"name": "血蚊"}]}])
    stats = c._get_skill_stats()
    assert len(stats) == 1
    assert stats[0]["skill"] == "先攻"
    assert stats[0]["count"] == 1
    assert stats[0]["values"] == ["30"]
    assert stats[0]["mons"][0]["name"] == "血蚊"


def test_skill_stats_dedup_same_skill_per_monster():
    c = FakeRead(
        monsters=[{"name": "血蚊",
                   "skill_items": [{"name": "先攻", "value": "30", "code": "1",
                                    "params": {}},
                                   {"name": "先攻", "value": "40", "code": "1",
                                    "params": {}}]}],
        history=[{"mons": [{"name": "血蚊"}]}])
    stats = c._get_skill_stats()
    assert stats[0]["count"] == 1      # 同一只怪重复技能只算一次


class FakeNotes(FakeRead):
    """带「用户写的介绍」和保存记录器的版本。"""

    def __init__(self, *args, notes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._skill_notes = dict(notes or {})
        self.saved = []
        self.changed = 0

    class _Sig:
        def __init__(self, owner):
            self.owner = owner

        def emit(self):
            self.owner.changed += 1

    @property
    def skillStatsChanged(self):
        return FakeNotes._Sig(self)


def _patch_saver(monkeypatch, c):
    import chaita.ui.controller.monsters.read as read_mod
    monkeypatch.setattr(read_mod, "_save_skill_notes",
                        lambda notes: c.saved.append(dict(notes)))


def test_技能介绍_用户写的优先_其次内置_再次老的怪上手写的():
    custom = {"name": "纳魔为攻", "effect": "老数据里写的", "custom": True}
    c = FakeNotes(monsters=[{"name": "铁卫", "skill_items": [custom]}],
                  notes={"破甲": "我改写的"})

    assert c._effect_of("破甲") == ("我改写的", "note")             # 改写优先
    text, source = c._effect_of("吸血")
    assert source == "builtin" and text != ""                        # 内置手册原话
    assert c._effect_of("纳魔为攻") == ("老数据里写的", "monster")    # 老数据读得出来
    assert c._effect_of("没人知道") == ("", "")
    assert c._effect_of("  ") == ("", "")


def test_set_skill_note_存下来_并通知界面(monkeypatch):
    c = FakeNotes()
    _patch_saver(monkeypatch, c)

    c.setSkillNote(" 纳魔为攻 ", "  魔防转攻击  ")

    assert c._skill_notes == {"纳魔为攻": "魔防转攻击"}
    assert c.saved == [{"纳魔为攻": "魔防转攻击"}]
    assert c.changed == 1
    assert c.skillEffect("纳魔为攻") == "魔防转攻击"


def test_set_skill_note_空或和原话一样_等于恢复原话(monkeypatch):
    from chaita.game import skillinfo
    builtin = skillinfo.effect_for("破甲")
    c = FakeNotes(notes={"破甲": "我改写的"})
    _patch_saver(monkeypatch, c)

    c.setSkillNote("破甲", builtin)                    # 和原话一字不差
    assert c._skill_notes == {}
    assert c.skillEffect("破甲") == builtin

    c._skill_notes = {"破甲": "我改写的"}
    c.setSkillNote("破甲", "   ")                      # 清空
    assert c._skill_notes == {}


def test_set_skill_note_没变就不写盘(monkeypatch):
    c = FakeNotes(notes={"破甲": "我改写的"})
    _patch_saver(monkeypatch, c)

    c.setSkillNote("破甲", "我改写的")                  # 一样
    c.setSkillNote("吸血", "")                          # 本来就没有改写
    c.setSkillNote("", "无名")                          # 没有技能名

    assert c.saved == [] and c.changed == 0


def test_skill_intro_带来源_和有没有改写过():
    c = FakeNotes(notes={"破甲": "我改写的", "纳魔为攻": "自己写的"})

    edited = c.skillIntro("破甲")
    assert edited == {"text": "我改写的", "source": "note",
                      "hasBuiltin": True, "edited": True}        # 内置的被改写了：可恢复
    own = c.skillIntro("纳魔为攻")
    assert own["source"] == "note" and own["hasBuiltin"] is False
    assert own["edited"] is False                                # 没有原话可恢复
    plain = c.skillIntro("吸血")
    assert plain["source"] == "builtin" and plain["edited"] is False
    assert c.skillIntro("没人知道")["text"] == ""


def test_skill_stats_的effect跟着用户改写走():
    c = FakeNotes(
        monsters=[{"name": "血蚊", "skill_items": [
            {"name": "破甲", "value": "50", "code": "7", "params": {}}]}],
        history=[{"mons": [{"name": "血蚊"}]}],
        notes={"破甲": "我改写的"})

    assert c._get_skill_stats()[0]["effect"] == "我改写的"


def test_skill_catalog_keeps_unknown_tokens():
    c = FakeRead(monsters=[{"name": "怪", "skills": "新技能"}])
    out = c._get_skill_catalog()
    assert "先攻" in out
    assert "新技能" in out
