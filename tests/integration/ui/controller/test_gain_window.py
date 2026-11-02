"""加属性收益窗口：**数值真值 + 它是自己一扇窗**（集成测试，只点界面上的东西）。

用户 2026-11-01："每增加 x 点攻击防御魔防，剩下的怪会减少多少伤害：对于每一只怪 /
对于每一种（一只 × 数量）/ 对于剩下所有怪，需要可以配上界，超过上界的按上界计算"，
随后："这是新功能！！！不要和之前的混在一起！！！"、"重新设计"。
→ 导航条 ＋ 开一扇自己的窗，和伤害计算没有关系（那边不许再挂这块）。

期望值**手算**（抄在每一条的说明里，不拿 damage_gain 比自己）：
  英雄 血 1000 / 攻 90 / 防 30；血蚊 1200 血 / 攻 60 / 防 20 / 带先攻：
    攻 90：ceil(1200/70)=18 回合 → 17 下 ×30 + 先攻 30 = 540
    攻 91：ceil(1200/71)=17 回合 → 16 下 ×30 + 30 = 510  → 每只少掉 30

标准见 `tests/integration/README.md`。
"""

from ... import helpers

HERO = {"hp": "1000", "atk": "90", "def": "30", "mdef": "0"}
HANDBOOK = [{"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
             "skill_items": [{"name": "先攻", "code": "", "params": {}}]}]


def _floor(name, mons):
    return {"floor": name, "url": "", "items": [], "grid": {"cells": []},
            "mons": mons}


# 两层：1层 血蚊 3 只 + 一个手册里没有的「鬼影」；2层 血蚊 1 只（另外 2 只已划掉）
TWO_FLOORS = [_floor("1层", [{"name": "血蚊", "count": 3},
                             {"name": "鬼影", "count": 1}]),
              _floor("2层", [{"name": "血蚊", "count": 1},
                             {"name": "血蚊", "count": 2, "done": True}])]


def _open(floors=None):
    """起真 Controller + QML，点导航条 ＋ 开「加属性收益」。"""
    controller, engine, window = helpers.make_controller()
    controller._last_status = dict(HERO)
    controller._monsters = [dict(one) for one in HANDBOOK]
    controller._map_history = floors if floors is not None else TWO_FLOORS
    controller.statusTextChanged.emit()
    controller.monstersChanged.emit()
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "gainOpen"))
    assert helpers.wait_for(
        lambda: window.property("gainWindow") is not None), "加属性收益窗口没打开"
    helpers.APP.processEvents()
    return controller, engine, window


def _panel(window):
    return helpers.find_item(window, "gainTotal")


def _total_text(window):
    return str(_panel(window).property("text"))


def _rows(window):
    return [" ".join(helpers.texts_of(row))
            for row in helpers.find_all(window, "gainRow")]


def _type(window, name, value):
    helpers.find_item(window, "gainField_" + name).setProperty("text", value)
    helpers.APP.processEvents()


def test_it_is_its_own_window_not_a_panel_of_the_damage_calculator():
    """测什么：导航条 ＋ 开的是**自己一扇窗**；伤害计算里那块面板已经拆干净了。

    交互顺序：① 点导航条 ＋ ② 断言 `gainWindow` 起来了、伤害计算没跟着开
    ③ 伤害计算窗口里找不到 `battleGain` / `battleGainPanel`（不许再挂回去）。
    """
    controller, engine, window = _open()
    panel = window.property("gainWindow")
    assert panel is not None
    assert panel.property("objectName") == "gainWindow"
    assert window.property("battleWindow") is None, "不许连带开伤害计算"

    # 两层各一组，组头写着这一层还剩几只
    groups = [" ".join(helpers.texts_of(group))
              for group in helpers.find_all(window, "gainGroup")]
    assert len(groups) == 2, groups
    assert "1层" in groups[0]

    # 伤害计算里那块「＋X 收益」已经整块删掉
    helpers.click_item(window, helpers.find_item(window, "battleOpen"))
    helpers.wait_for(lambda: window.property("battleWindow") is not None)
    helpers.APP.processEvents()
    assert helpers.find_item(window, "battleGain") is None
    assert helpers.find_item(window, "battleGainPanel") is None


def test_typing_an_attack_point_saves_thirty_blood_per_bug():
    """测什么：攻 +1 → 血蚊每只少掉 30；两层加起来 4 只 = 120。

    手算：血蚊 540 → 510，每只少 30；1层 3 只 + 2层 1 只（划掉的 2 只不算）= 120。

    交互顺序：① 开窗 ② 「攻」那格填 1 ③ 读每种那一行 + 底下的合计。
    """
    controller, engine, window = _open()
    _type(window, "atk", "1")

    rows = _rows(window)
    assert len(rows) == 2, rows          # 1层一行血蚊、2层一行血蚊
    assert "一只 30" in rows[0] and "共 90" in rows[0], rows[0]
    assert "一只 30" in rows[1] and "共 30" in rows[1], rows[1]
    assert "少掉 120 血" in _total_text(window), _total_text(window)


def test_the_upper_bound_caps_the_total_but_not_each_species():
    """测什么：上界 20 → 合计写 20 并说明"本来 120"，每种那两列照实写。

    交互顺序：① 开窗、攻 +1（合计 120）② 「上界」填 20
    ③ 合计那行变成 20 + 本来 120；血蚊那行还是 一只 30 / 共 90。
    """
    controller, engine, window = _open()
    _type(window, "atk", "1")
    assert "少掉 120 血" in _total_text(window)

    _type(window, "cap", "20")
    text = _total_text(window)
    assert "少掉 20 血" in text and "本来 120" in text, text
    assert "按上界 20" in text, text
    assert "共 90" in " ".join(_rows(window)), "单种不封，照实写"


def test_a_monster_without_handbook_values_is_listed_but_not_counted():
    """测什么：手册里没有数值的「鬼影」照样列出来、写明没算、不进合计。

    交互顺序：① 开窗、攻 +1 ② 找 `gainUnknown` 那一行
    ③ 断言写着「鬼影」和原因；合计仍是血蚊那 120（没给鬼影编数字）。
    """
    controller, engine, window = _open()
    _type(window, "atk", "1")

    unknown = helpers.find_all(window, "gainUnknown")
    assert len(unknown) == 1, "只有鬼影是查不到的"
    text = " ".join(helpers.texts_of(unknown[0]))
    assert "鬼影" in text and "手册里没有它的数值" in text, text
    assert "少掉 120 血" in _total_text(window), _total_text(window)


def test_before_you_type_anything_it_says_how_to_use_it():
    """测什么：一个加成都没填 → 底下不摆"少掉 0"，而是告诉你填一个。

    交互顺序：① 开窗 ② 什么都不填 → 合计那行是用法提示。
    """
    controller, engine, window = _open()
    assert "填一个加成" in _total_text(window), _total_text(window)


def test_when_nothing_is_left_the_window_says_so():
    """测什么：剩下的怪全划掉了 → 空态文案，合计那行不写 0。

    交互顺序：① 清单里只有已划掉的怪 ② 开窗 → 空态 + 合计为空。
    """
    controller, engine, window = _open(
        [_floor("3层", [{"name": "血蚊", "count": 2, "done": True}])])
    _type(window, "atk", "1")

    assert helpers.find_item(window, "gainEmpty").property("visible") is True
    assert helpers.find_all(window, "gainRow") == []
    assert _total_text(window) == "", _total_text(window)


def test_the_upper_bound_starts_at_your_current_hp():
    """测什么：第一次打开就把上界填成"我现在有多少血"（省不下来比血还多的血）。

    交互顺序：① 状态行读到 血 1000 ② 点导航条 ＋ ③ 「上界」那格已经是 1000，
    合计照实写 120（没超过上界，不封）。
    """
    controller, engine, window = _open()
    assert helpers.find_item(window, "gainField_cap").property("text") == "1000"
    _type(window, "atk", "1")
    assert "少掉 120 血" in _total_text(window), _total_text(window)
    assert "按上界" not in _total_text(window)


def test_clicking_a_row_takes_you_to_that_cell_on_the_map():
    """测什么：点收益表里一行 → 地图切到那一层、圈出这一格（不用自己去图上找）。

    交互顺序：① 1层 清单里血蚊标在 (1,2)（第 2 行第 3 列）② 打开窗口
    ③ 点血蚊那一行 → `mapHiFloor/mapHiRow/mapHiCol` 指到 1层 (1,2)。
    """
    floor = _floor("1层", [{"name": "血蚊", "count": 1}])
    floor["grid"] = {"cells": [{"kind": "monster", "name": "血蚊",
                                "effect": "", "row": 1, "col": 2}]}
    controller, engine, window = _open([floor])

    row = helpers.find_all(window, "gainRow")[0]
    assert "2,3" in " ".join(helpers.texts_of(row)), "行上要写清它在哪一格"
    helpers.click_item(window, helpers.find_item(window, "gainRowClick"))
    helpers.APP.processEvents()

    assert str(window.property("mapHiFloor")) == "1层"
    assert int(window.property("mapHiRow")) == 1
    assert int(window.property("mapHiCol")) == 2


def test_the_numbers_you_typed_are_still_there_when_you_reopen():
    """测什么：关掉再打开，填过的加成还在（状态在主窗口上，窗口只是画和点）。

    交互顺序：① 开窗、攻 +1（合计 120）② 点 ✕ 关掉 ③ 再点导航条 ＋
    → 那格还写着 1，合计还是 120。
    """
    controller, engine, window = _open()
    _type(window, "atk", "1")
    assert "少掉 120 血" in _total_text(window)

    helpers.click_item(window, helpers.find_item(window, "gainClose"))
    assert helpers.wait_for(lambda: window.property("gainWindow") is None), "窗口没关掉"

    helpers.click_item(window, helpers.find_item(window, "gainOpen"))
    assert helpers.wait_for(
        lambda: window.property("gainWindow") is not None), "窗口没重新打开"
    helpers.APP.processEvents()

    assert helpers.find_item(window, "gainField_atk").property("text") == "1"
    assert "少掉 120 血" in _total_text(window), _total_text(window)
