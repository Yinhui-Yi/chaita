"""技能介绍卡（**集成测试**，真点击技能胶囊、真改文字）。

规则：
  · 点技能胶囊 → 弹出这个技能的介绍卡；内置的常见技能显示游戏手册原话（只读的底）；
  · 介绍可以改写（不同魔塔数值不同）：改完点别处就存，优先显示，「恢复原话」还原；
  · 内置表里没有的技能：空白文本框，用户自己写；
  · 介绍卡开着时，主窗口的 Esc（会退出软件）要让位给它。

标准见 `tests/integration/README.md`。用户的介绍存在内存里（测试里不写真实的 skill_notes.json）。
"""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent

from chaita.game import skillinfo

from ... import helpers

BUILTIN = "破甲"
CUSTOM = "纳魔为攻"


def _window():
    controller, engine, window = helpers.make_controller()
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20", "skills": BUILTIN},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30", "skills": CUSTOM}]
    controller._map_history = [{
        "floor": "3层", "url": "", "mons": [{"name": "血蚊", "count": 2},
                                           {"name": "铁卫", "count": 1}],
        "items": [], "grid": {"cells": []}, "routes": []}]
    controller.monstersChanged.emit()
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    window.setProperty("mapCollapsed", True)
    window.setProperty("monCollapsed", True)
    helpers.APP.processEvents()
    return controller, engine, window


def _chip(window, name):
    for chip in helpers.find_all(window, "skillRow"):
        label = [n for n in _walk(chip) if n.objectName() == "skillName"]
        if label and label[0].property("text") == name:
            return chip
    raise AssertionError("没找到技能胶囊 %s" % name)


def _walk(item):
    stack = [item]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.childItems())


def _open(window, name):
    helpers.click_item(window, _chip(window, name))
    helpers.APP.processEvents()
    assert helpers.wait_for(
        lambda: helpers.find_item(window, "skillIntroName") is not None
        and helpers.find_item(window, "skillIntroName").isVisible()), "介绍卡没弹出来"


def _close(window):
    """按 Esc 关掉介绍卡（和用户一样）：卡关掉，改过的字就存下来。

    介绍卡开着时主窗口的 Esc（退出软件）要让位给它，所以这一下只关卡、不退出。
    """
    for kind in (QEvent.KeyPress, QEvent.KeyRelease):
        helpers.APP.sendEvent(window, QKeyEvent(kind, Qt.Key_Escape, Qt.NoModifier))
    helpers.APP.processEvents()
    def closed():
        name = helpers.find_item(window, "skillIntroName")
        return name is None or not name.isVisible()

    assert helpers.wait_for(closed, timeout=3), "Esc 没把介绍卡关掉"


def _set_text(window, text):
    field = helpers.find_item(window, "skillIntroEffect")
    helpers.focus_field(field)
    field.setProperty("text", text)
    helpers.APP.processEvents()


def test_点技能胶囊弹出介绍卡_内置技能显示手册原话():
    """测什么：点「破甲」→ 卡上写着技能名、手册原话（来源「手册原话」）、带它的怪。

    走过的界面：主界面技能卡 → 技能介绍卡。
    """
    controller, engine, window = _window()
    _open(window, BUILTIN)

    assert helpers.find_item(window, "skillIntroName").property("text") == BUILTIN
    assert helpers.find_item(window, "skillIntroEffect").property("text") \
        == skillinfo.effect_for(BUILTIN) != ""
    assert helpers.find_item(window, "skillIntroSource").property("text") == "手册原话"
    assert not helpers.find_item(window, "skillIntroRestore").isVisible()
    assert len(helpers.find_all(window, "skillIntroMonster")) == 1


def test_改写内置介绍_点别处就存_恢复原话还原():
    """测什么：把「破甲」的介绍改成自己的话，点卡外面 → 存下来，来源变「已改写」；
    再点开仍是改写的；点「恢复原话」→ 回到手册原话、不再有改写记录。

    走过的界面：技能介绍卡（文本框、恢复原话）。
    """
    controller, engine, window = _window()
    _open(window, BUILTIN)
    _set_text(window, "战斗前，怪物附加角色防御的 40% 作为伤害")
    _close(window)
    assert controller._skill_notes == {BUILTIN: "战斗前，怪物附加角色防御的 40% 作为伤害"}

    _open(window, BUILTIN)
    assert helpers.find_item(window, "skillIntroEffect").property("text") \
        == "战斗前，怪物附加角色防御的 40% 作为伤害"
    assert helpers.find_item(window, "skillIntroSource").property("text") == "已改写"
    restore = helpers.find_item(window, "skillIntroRestore")
    assert restore.isVisible()

    helpers.click_item(window, restore)
    assert controller._skill_notes == {}
    assert helpers.find_item(window, "skillIntroEffect").property("text") \
        == skillinfo.effect_for(BUILTIN)
    assert helpers.find_item(window, "skillIntroSource").property("text") == "手册原话"


def test_内置表里没有的技能_空白框自己写_写完存下来():
    """测什么：「纳魔为攻」不在内置表里 → 文本框是空的、来源「还没有介绍」；
    写一句点别处 → 存下来，来源变「自己写的」。

    走过的界面：技能介绍卡。
    """
    assert skillinfo.effect_for(CUSTOM) == ""
    controller, engine, window = _window()
    _open(window, CUSTOM)
    assert helpers.find_item(window, "skillIntroEffect").property("text") == ""
    assert helpers.find_item(window, "skillIntroSource").property("text") == "还没有介绍"

    _set_text(window, "把对方魔防转成自己的攻击")
    _close(window)
    assert controller._skill_notes == {CUSTOM: "把对方魔防转成自己的攻击"}

    _open(window, CUSTOM)
    assert helpers.find_item(window, "skillIntroSource").property("text") == "自己写的"
    assert controller.skillEffect(CUSTOM) == "把对方魔防转成自己的攻击"


def test_介绍卡开着时Esc让位_关掉后恢复():
    """测什么：介绍卡开着时 `skillIntroOpen` 为真（主窗口的 Esc 看它：不然 Esc 会把整个软件关了）；
    卡关掉后恢复为假。

    走过的界面：技能介绍卡 + 主窗口 Esc 开关。
    """
    controller, engine, window = _window()
    assert window.property("skillIntroOpen") is False
    _open(window, BUILTIN)
    assert window.property("skillIntroOpen") is True
    _close(window)
    assert window.property("skillIntroOpen") is False


def test_介绍卡不会超出窗口_点最底下的胶囊也在窗口里():
    """测什么：介绍卡的位置夹在窗口里（左右不出界；下面放不下翻到胶囊上面）。

    走过的界面：技能介绍卡的摆位。
    """
    controller, engine, window = _window()
    _open(window, BUILTIN)
    name = helpers.find_item(window, "skillIntroName")
    top_left = name.mapToScene(QPointF(0, 0))
    assert top_left.x() >= 0 and top_left.y() >= 0
    assert top_left.x() + name.width() <= window.width()
    assert top_left.y() + name.height() <= window.height()
