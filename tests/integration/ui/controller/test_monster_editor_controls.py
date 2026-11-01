"""怪物编辑卡片上的控件（**集成测试**，只点界面上的东西）。

覆盖：加技能（从下拉里选 / 自定义一条）、技能参数框、删掉正在编辑的这只、打开图标
选择器（翻页/搜索/选一张/关闭）、四个数值框、保存与关闭。以前只测过 `saveMonsterFull`
这类 Slot，**卡片到 Slot 的接线没人跑过**：下拉里选的技能是不是落到这一只、删的是不是
正在编辑的这一只、关掉之后草稿有没有残留。

标准见 `tests/integration/README.md`。驱动：点主界面怪物行打开卡片，之后全部点卡片里的
控件 / 在输入框里打字。断言读公开属性（`controller.monsters`、`window.monEdit/monSkills/
iconPicker/iconQuery…`）。起点数据（怪物库）直接摆。

注释按「测什么 / 交互顺序」写；界面多半只有一扇卡片，顺序才是这里要交代的东西。
"""

from ... import helpers


def _editor(monsters=None):
    """摆好怪物库，点第一行把编辑卡片打开。"""
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


def _type(window, item, text):
    """在输入框里打字（真实键盘事件收尾，和用户敲回车一样）。"""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    item.forceActiveFocus()
    helpers.APP.processEvents()
    item.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(item.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def test_skill_picker_adds_skill_and_save_keeps_it():
    """测什么：加一条技能后保存，写进的是这只怪。

    交互顺序：① 怪物区点第一行开卡片 ② 点技能「＋」开下拉 ③ 点下拉第一行
    ④ 点卡片「保存」→ 断言 `controller.monsters[0].skill_items` 就是刚选的那条。
    """
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

    saved = controller.monsters[0].get("skill_items") or []
    assert [s["name"] for s in saved] == [picked[0]["name"]]


def test_delete_button_removes_that_monster():
    """测什么：卡片上的删除只删正在编辑的这一只，删完卡片关掉。

    交互顺序：① 怪物区点第一行（血蚊）开卡片 ② 点「删除」→ 断言库里只剩铁卫、
    `monEdit == -1`。
    """
    controller, engine, window = _editor()

    helpers.click_item(window, helpers.find_item(window, "monDelete"))
    helpers.APP.processEvents()

    assert [m["name"] for m in controller.monsters] == ["铁卫"]
    assert window.property("monEdit") == -1


def test_icon_picker_opens_from_editor():
    """测什么：点缩略图能开素材库，里面真有一堆图可点。

    交互顺序：① 怪物区点第一行开卡片 ② 点卡片上的缩略图 → 断言素材库打开且图格子非空。
    """
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()

    assert window.property("iconPicker") is True
    assert len(helpers.find_all(window, "iconCell")) > 0


# ---- 图标选择器：点一张图 → 记下 id → 保存时写进怪物 ----

def test_icon_cell_pick_closes_picker_and_saves_icon():
    """测什么：图库选一张 → 图库关掉、卡片记下 id；保存后写进这只怪。

    交互顺序：① 开卡片 ② 点缩略图开图库 ③ 点第一张图（图库自动关）④ 点「保存」
    → 断言 `monsters[0].icon_id` 就是刚选的 id。
    """
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

    assert controller.monsters[0].get("icon_id") == picked


def test_icon_picker_tabs_and_search(monkeypatch):
    """测什么：图库的两个页签来回切，列表跟着变、不炸。

    交互顺序：① 开卡片 ② 点缩略图开图库 ③ 点「搜索」页 ④ 点回「emoji」页
    → 断言两次 `iconSearchMode` 和格子数量回到原样。
    """
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()
    total = len(helpers.find_all(window, "iconCell"))

    helpers.click_item(window, helpers.find_item(window, "iconTabSearch"))
    helpers.APP.processEvents()
    assert window.property("iconSearchMode") is True

    helpers.click_item(window, helpers.find_item(window, "iconTabEmoji"))
    helpers.APP.processEvents()
    assert window.property("iconSearchMode") is False
    assert len(helpers.find_all(window, "iconCell")) == total


def test_icon_picker_close_button():
    """测什么：图库的关闭只关图库，卡片不动。

    交互顺序：① 开卡片 ② 点缩略图开图库 ③ 点图库关闭 → 断言 `iconPicker` 为假。
    """
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monIconPick"))
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "iconClose"))
    helpers.APP.processEvents()

    assert window.property("iconPicker") is False


# ---- 技能参数的框：改完要落进这只怪 ----

def test_skill_param_field_writes_into_skill():
    """测什么：技能参数改了要进卡片草稿，保存后进这只怪。

    交互顺序：① 怪物区点那一行（带「破甲」的怪）开卡片 ② 参数框打 50 回车
    ③ 点「保存」→ 断言草稿和库里都是 `params.defValue == "50"`。
    """
    controller, engine, window = _editor(monsters=[
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
         "skill_items": [{"name": "破甲", "value": "", "code": "7",
                          "params": {"defValue": "10"}}]}])
    fields = helpers.find_all(window, "monSkillParam")
    assert fields, "破甲的参数格没画出来"

    _type(window, fields[0], "50")

    assert _skills(window)[0]["params"]["defValue"] == "50"

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()
    saved = controller.monsters[0]["skill_items"][0]
    assert saved["name"] == "破甲"
    assert saved["params"]["defValue"] == "50"


def test_custom_skill_name_and_effect_are_saved():
    """测什么：自定义技能的名字和效果都写进这只怪。

    交互顺序：① 开卡片 ② 点技能「＋」 ③ 点下拉里的「自定义」 ④ 名字框打字回车
    ⑤ 效果框打字 ⑥ 点「保存」→ 断言 `skill_items[0]` 的 name/custom/effect。
    """
    controller, engine, window = _editor()
    helpers.click_item(window, helpers.find_item(window, "monSkillPick"))
    helpers.APP.processEvents()
    helpers.click_item(window, helpers.find_item(window, "skillPickCustom"))
    helpers.APP.processEvents()

    _type(window, helpers.find_item(window, "monSkillName"), "每回合回血")

    effect = helpers.find_item(window, "monSkillEffectEdit")
    effect.setProperty("text", "每回合回 5%")
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()

    saved = controller.monsters[0]["skill_items"][0]
    assert saved["name"] == "每回合回血"
    assert saved["custom"] is True
    assert saved["effect"] == "每回合回 5%"


def test_close_button_closes_editor_without_saving():
    """测什么：关闭（不是保存）之后库里一个字没变。

    交互顺序：① 开卡片 ② 点关闭 → 断言 `monEdit == -1` 且这只怪的字段和打开前一模一样。
    """
    controller, engine, window = _editor()
    before = [dict(m) for m in controller.monsters]

    helpers.click_item(window, helpers.find_item(window, "monClose"))
    helpers.APP.processEvents()

    assert window.property("monEdit") == -1
    assert [dict(m) for m in controller.monsters] == before


# ---- 图库里那个搜索框 ----

def test_icon_search_filters_the_grid():
    """测什么：搜索框打「史莱姆」只剩匹配的图，清空又全回来。

    交互顺序：① 开卡片 ② 点缩略图开图库 ③ 搜索框打「史莱姆」 ④ 清空搜索框
    → 断言格子数量：全部 > 过滤后 > 0，清空后回到全部。
    """
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
    """测什么：血量和金币改完保存，写进这只怪，名字没被顺手改掉。

    交互顺序：① 开卡片 ② 血量框打 1500 回车 ③ 金币框打 999 回车 ④ 点「保存」
    → 断言 hp/gold 变了、name 还是「血蚊」。
    """
    controller, engine, window = _editor()
    _type(window, helpers.find_item(window, "monHpField"), "1500")
    _type(window, helpers.find_item(window, "monGoldField"), "999")

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()

    saved = controller.monsters[0]
    assert saved["hp"] == "1500"
    assert saved["gold"] == "999"
    assert saved["name"] == "血蚊"          # 别的字段别被顺手改掉
