"""怪物编辑卡片上的控件（真点击）：加技能并从下拉里选、删掉这只、打开图标选择、关闭。

以前只测过 `saveMonsterFull` 这类 Slot，**卡片到 Slot 的接线没人跑过**：技能下拉里选的
是不是这一只、删的是不是正在编辑的这一只、关掉之后草稿有没有残留。
"""

from ... import helpers


def _editor(monsters=None):
    controller, engine, window = helpers.make_controller()
    controller._monsters = monsters or [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    controller.monstersChanged.emit()
    helpers.APP.processEvents()
    helpers.click_item(window, helpers.find_all(window, "monOpen")[0])
    helpers.APP.processEvents()
    return controller, engine, window


def _skills(window):
    value = window.property("monSkills")
    return value.toVariant() if hasattr(value, "toVariant") else value


def test_skill_picker_adds_skill_and_save_keeps_it():
    controller, engine, window = _editor()
    assert _skills(window) == []

    helpers.click_item(window, helpers.find_item(window, "monSkillPick"))
    helpers.APP.processEvents()
    assert window.property("skillPicker") is True

    rows = helpers.find_all(window, "skillPickRow")
    assert rows, "技能下拉里应该有技能可选"
    helpers.click_item(window, rows[0])
    helpers.APP.processEvents()
    picked = _skills(window)
    assert len(picked) == 1
    assert picked[0]["name"] != ""

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()

    saved = controller._monsters[0].get("skill_items") or []
    assert [s["name"] for s in saved] == [picked[0]["name"]]


def test_delete_button_removes_that_monster():
    controller, engine, window = _editor()

    helpers.click_item(window, helpers.find_item(window, "monDelete"))
    helpers.APP.processEvents()

    assert [m["name"] for m in controller._monsters] == ["铁卫"]
    assert window.property("monEdit") == -1


def test_icon_picker_opens_from_editor():
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()

    assert window.property("iconPicker") is True
    # 打开之后得真有一堆图能点（不然是个空壳）
    assert len(helpers.find_all(window, "iconCell")) > 0


# ---- 图标选择器：点一张图 → 记下 id → 保存时写进怪物 ----

def test_icon_cell_pick_closes_picker_and_saves_icon():
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()

    cells = helpers.find_all(window, "iconCell")
    assert cells, "图库至少要有素材可选"
    chosen = cells[0]

    helpers.click_item(window, chosen)
    helpers.APP.processEvents()

    assert window.property("iconPicker") is False
    picked = str(window.property("monIconId") or "")
    assert picked != ""

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()

    saved = controller._monsters[0]
    assert saved.get("icon_id") == picked


def test_icon_picker_tabs_and_search(monkeypatch):
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()
    total = len(helpers.find_all(window, "iconCell"))

    # 切到「搜索/emoji」那页：列表变了（这里只要求切得过去且不炸）
    helpers.click_item(window, helpers.find_item(window, "iconTabSearch"))
    helpers.APP.processEvents()
    assert window.property("iconSearchMode") is True

    helpers.click_item(window, helpers.find_item(window, "iconTabEmoji"))
    helpers.APP.processEvents()
    assert window.property("iconSearchMode") is False
    assert len(helpers.find_all(window, "iconCell")) == total


def test_icon_picker_close_button():
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "iconClose"))
    helpers.APP.processEvents()

    assert window.property("iconPicker") is False


# ---- 技能参数的框：改完要落进这只怪 ----

def test_skill_param_field_writes_into_skill():
    controller, engine, window = _editor(monsters=[
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "破甲", "value": "", "code": "7",
                          "params": {"defValue": "10"}}]}])
    # 破甲有一个百分比参数 → 卡片上应该有一格能改
    fields = helpers.find_all(window, "monSkillParam")
    assert fields, "破甲的参数格没画出来"

    field = fields[0]
    field.forceActiveFocus()
    helpers.APP.processEvents()
    field.setProperty("text", "50")
    helpers.APP.processEvents()

    assert _skills(window)[0]["params"]["defValue"] == "50"

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()
    saved = controller._monsters[0]["skill_items"][0]
    assert saved["name"] == "破甲"
    assert saved["params"]["defValue"] == "50"


def test_custom_skill_name_and_effect_are_saved():
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monSkillPick"))
    helpers.APP.processEvents()
    helpers.click_item(window, helpers.find_item(window, "skillPickCustom"))
    helpers.APP.processEvents()

    name = helpers.find_item(window, "monSkillName")
    name.forceActiveFocus()
    helpers.APP.processEvents()
    name.setProperty("text", "每回合回血")
    from PySide6.QtCore import QEvent, Qt as _Qt
    from PySide6.QtGui import QKeyEvent
    helpers.APP.sendEvent(name.window(),
                          QKeyEvent(QEvent.KeyPress, _Qt.Key_Return,
                                    _Qt.NoModifier))
    helpers.APP.processEvents()

    effect = helpers.find_item(window, "monSkillEffectEdit")
    effect.setProperty("text", "每回合回 5%")
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()

    saved = controller._monsters[0]["skill_items"][0]
    assert saved["name"] == "每回合回血"
    assert saved["custom"] is True
    assert saved["effect"] == "每回合回 5%"


def test_close_button_closes_editor_without_saving():
    controller, engine, window = _editor()
    before = [dict(m) for m in controller._monsters]

    helpers.click_item(window, helpers.find_item(window, "monClose"))
    helpers.APP.processEvents()

    assert window.property("monEdit") == -1
    assert controller._monsters == before


# ---- 图库里那个搜索框 ----

def test_icon_search_filters_the_grid():
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()
    before = len(helpers.find_all(window, "iconCell"))
    assert before > 0

    search = helpers.find_item(window, "iconSearch")
    search.setProperty("text", "史莱姆")
    helpers.APP.processEvents()

    assert str(window.property("iconQuery")) == "史莱姆"
    after = helpers.find_all(window, "iconCell")
    assert 0 < len(after) < before          # 过滤之后变少，但不是空

    search.setProperty("text", "")
    helpers.APP.processEvents()
    assert len(helpers.find_all(window, "iconCell")) == before


# ---- 数值框（Labeled 里的 TextField，名字是 容器名 + "Field"）----

def test_hp_and_gold_fields_save_into_monster():
    controller, engine, window = _editor()
    for name, value in (("monHpField", "1500"), ("monGoldField", "999")):
        field = helpers.find_item(window, name)
        assert field is not None, name + " 没找到"
        field.forceActiveFocus()
        helpers.APP.processEvents()
        field.setProperty("text", value)
        helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()

    saved = controller._monsters[0]
    assert saved["hp"] == "1500"
    assert saved["gold"] == "999"
    assert saved["name"] == "血蚊"          # 别的字段别被顺手改掉
