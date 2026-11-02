"""「这一层」小窗上剩下的控件（**集成测试**，真点击/真打字）。

覆盖：地图那一栏的「编辑」开关、怪名只读、点「路线 1」开链窗口、✕ 关窗、「＋」开下一层、
编辑模式下行的"位置 1,1"跟着格子变、路线那半截实时数值、右下角拉大小。

真值手写：编辑按钮点一下进编辑（文字变「完成」）、再点退出；怪名点不动；点「路线 1」把
那条路线打开；✕ 关掉这扇窗；「＋」开下一层。

标准见 `tests/integration/README.md`。驱动：点「清单 ›」开窗 → 点窗/地图条上的控件，
或在图上右键/把格子拖到行上（真 drop 事件）。断言读公开属性（`window.floorWindows /
routeWindow / routeFloor / floorSizes`、界面文字）。
"""

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from .... import helpers


def _sheet(floors=None, mons=None, routes=None):
    """摆好层记录，再点「清单 ›」把这层的小窗打开。"""
    controller, engine, window = helpers.make_controller()
    controller._last_status = {"hp": "1000", "atk": "90", "def": "30",
                               "mdef": "10"}
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"}]
    # 怪物行读的是缓存属性，不发信号界面还拿着上一轮的名单
    controller.monstersChanged.emit()
    entries = []
    for floor in floors or ["长安1"]:
        entries.append({
            "floor": floor, "url": "",
            "mons": list(mons or []), "items": [],
            "grid": {"cells": []}, "routes": list(routes or [])})
    controller._map_history = entries
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    assert helpers.wait_for(
        lambda: helpers.find_item(window, "mapSheet") is not None), \
        "地图那一栏没出来"
    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf(entries[0]["floor"]) is not None), \
        "清单没打开"
    helpers.APP.processEvents()
    return controller, engine, window


def _type(window, item, text):
    """在输入框里打完字再按回车（走 editingFinished）。"""
    helpers.focus_field(item)
    item.setProperty("text", text)
    helpers.APP.processEvents()
    helpers.APP.sendEvent(item.window(),
                          QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                    Qt.NoModifier))
    helpers.APP.processEvents()


def _windows(window):
    value = window.property("floorWindows")
    return value.toVariant() if hasattr(value, "toVariant") else value


def test_grid_edit_button_lives_in_the_map_strip():
    """测什么：编辑开关在地图那条动作里，点一下退出（文字变「编辑」），再点又进编辑。

    交互顺序：① 点「清单 ›」开这一层 —— **开清单会自动进编辑模式**，所以按钮此时写
    「完成」 ② 点「完成」→ 断言 `gridEditOn` 为假、文字变「编辑」 ③ 再点一次 → 断言
    又进编辑；小窗里没有那个旧按钮（它以前在地图截图右上角）。
    """
    controller, engine, window = _sheet()
    helpers.APP.processEvents()

    button = helpers.find_item(window, "mapGridEdit")
    assert button is not None
    # 开清单 = 自动进编辑（用户："我怎么标？"）
    assert window.property("gridEditOn") is True
    assert button.property("text") == "完成"

    helpers.click_item(window, button)
    assert window.property("gridEditOn") is False
    assert helpers.find_item(window, "mapGridEdit").property("text") == "编辑"

    helpers.click_item(window, helpers.find_item(window, "mapGridEdit"))
    assert window.property("gridEditOn") is True
    assert helpers.find_item(window, "floorGridEdit") is None


def test_monster_name_is_read_only():
    """测什么：清单里的怪名是只读文本，点它/往里打字都改不动数据。

    交互顺序：① 点「清单 ›」开这一层（有一只血蚊）② 点那一行的名字 ③ 直接改那个控件的
    text 再回车 → 断言控件是 Text（没有 placeholderText）、数据里还是「血蚊」。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    field = helpers.find_item(window, "floorMonName")
    assert field is not None
    # 它是 Text 不是 TextField：没有 placeholderText / 没有可编辑的输入框
    assert field.property("placeholderText") is None
    assert field.property("text") == "血蚊"
    _type(window, field, "血蚊王")
    rows = window.sheetMons("长安1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["name"] == "血蚊"


def test_close_button_closes_the_sheet():
    """测什么：点小窗右上角的 ✕ → 这扇窗关掉。

    交互顺序：① 点「清单 ›」开这一层 ② 点 ✕ → 断言 `floorWindows` 空了。
    """
    controller, engine, window = _sheet()
    helpers.click_item(window, helpers.find_item(window, "floorClose"))
    helpers.APP.processEvents()

    assert _windows(window) == []


def test_next_button_switches_to_the_next_floor_in_place():
    """测什么：点标题行的「›」→ 开下一层的清单、关掉这一层，不多开一扇窗。

    交互顺序：① 点「清单 ›」开长安1 ② 点「›」→ 断言只剩长安2 的窗，且落在原来的位置。
    """
    controller, engine, window = _sheet(floors=["长安1", "长安2"])
    before = window.floorSheetOf("长安1")
    spot = (before.x(), before.y())

    helpers.click_item(window, helpers.find_item(window, "floorNext"))
    assert helpers.wait_for(lambda: window.floorSheetOf("长安2") is not None)
    helpers.APP.processEvents()

    assert _windows(window) == ["长安2"]
    after = window.floorSheetOf("长安2")
    assert (after.x(), after.y()) == spot


def test_prev_button_goes_back_and_does_nothing_at_the_ends():
    """测什么：「‹」回上一层；在第一层 / 最后一层点到头的那个键没有反应。"""
    controller, engine, window = _sheet(floors=["长安1", "长安2"])

    helpers.click_item(window, helpers.find_item(window, "floorPrev"))
    helpers.APP.processEvents()
    assert _windows(window) == ["长安1"], "第一层没有上一层，不该动"

    helpers.click_item(window, helpers.find_item(window, "floorNext"))
    assert helpers.wait_for(lambda: window.floorSheetOf("长安2") is not None)
    helpers.click_item(window, helpers.find_item(window, "floorNext"))
    helpers.APP.processEvents()
    assert _windows(window) == ["长安2"], "最后一层没有下一层，不该动"

    helpers.click_item(window, helpers.find_item(window, "floorPrev"))
    assert helpers.wait_for(lambda: window.floorSheetOf("长安1") is not None)
    assert _windows(window) == ["长安1"]


# ---- 三段（楼梯 / 怪物 / 资源）一页排下来 ----

def test_sections_are_on_one_page_in_order_with_counts():
    """测什么：楼梯、怪物、资源三段一页排下来（楼梯最上），标题上写各自的条数，不用切页。

    交互顺序：① 开清单（1 只怪 + 1 个资源 + 1 个楼梯）② 三个段标题都看得见、从上到下是
    楼梯 → 怪物 → 资源 ③ 怪行、楼梯行同时在可见区里，每段都有自己的「＋ 加…」。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    controller._map_history[0]["items"] = [
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1}]
    controller.addStair("长安1", "up")
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    heads = [helpers.find_item(window, name)
             for name in ("floorSecStair", "floorSecMon", "floorSecItem")]
    ys = [head.mapToScene(QPointF(0, 0)).y() for head in heads]
    assert ys == sorted(ys), "段的顺序应是 楼梯 → 怪物 → 资源"
    for head, text in zip(heads, ("楼梯", "怪物", "资源")):
        assert text in helpers.texts_of(head)
        assert "1" in helpers.texts_of(head)
    assert len(helpers.find_all(window, "floorStairRow")) == 1
    assert len(helpers.find_all(window, "floorMonRow")) == 1
    for name in ("floorAddStair", "floorAddMon", "floorAddItem"):
        assert helpers.find_item(window, name).isVisible()


def test_section_head_folds_and_unfolds_its_rows():
    """测什么：点段标题 = 折起 / 展开这一段的行；折起的行不接拖放（`rowAt` 不认）。"""
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    assert len(helpers.find_all(window, "floorMonRow")) == 1

    helpers.click_item(window, helpers.find_item(window, "floorSecMonToggle"))
    assert helpers.find_all(window, "floorMonRow") == []
    assert helpers.find_item(window, "floorSecMon").property("open") is False

    helpers.click_item(window, helpers.find_item(window, "floorSecMonToggle"))
    assert len(helpers.find_all(window, "floorMonRow")) == 1


# ---- 标位置：行尾胶囊 + 底部「已选」条 ----

def test_position_chip_shows_the_coordinate_of_the_marked_cell():
    """测什么：编辑模式下把一格拖到怪那一行 → 行尾胶囊从「未标」变成这一格的坐标「1,1」。

    交互顺序：① 点「清单 ›」开这一层（**自动进编辑模式**）② 把 (1,1) 这一格拖到
    怪那一行上松手 → 断言 `floorMonPos` 先写「未标」、之后写「1,1」（1 开始）。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    chip = helpers.find_item(window, "floorMonPos")
    assert helpers.texts_of(chip) == ["未标"]

    assert window.property("gridEditOn") is True, "开清单应该自动进编辑模式"

    row = helpers.find_all(window, "floorMonRow")[0]
    helpers.drop_cells(window, row, {"row": 0, "col": 0})
    helpers.APP.processEvents()

    assert helpers.texts_of(helpers.find_item(window, "floorMonPos")) == ["1,1"]


def test_clicking_the_row_selects_the_entry_and_shows_its_cells():
    """测什么：点**整行** = 选中这个词条（地图上圈出它的格子）；底部「已选」条写出
    名字和每一格（1 开始），行尾胶囊写第一格加「+N」。再点一次取消。

    交互顺序：① 开清单，把 (1,1) 和 (3,4) 两格拖给血蚊 ② 还没选时底部没有「已选」条
    ③ 点血蚊那一行的空白处 → 条出现，写「已选：血蚊   1,1 · 3,4」，胶囊写「1,1 +1」，
    `gridSelected` 是血蚊 ④ 再点 → 取消选中。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 2}])
    row = helpers.find_all(window, "floorMonRow")[0]
    helpers.drop_cells(window, row, {"cells": [{"row": 0, "col": 0},
                                               {"row": 2, "col": 3}]})
    helpers.APP.processEvents()
    assert not helpers.find_item(window, "floorSelectedStrip").isVisible()

    helpers.click_item(window, helpers.find_item(window, "floorMonSelect"))

    assert window.property("gridSelected") == "血蚊"
    assert helpers.find_item(window, "floorSelectedStrip").isVisible()
    assert helpers.find_item(window, "floorSelectedText").property("text") \
        == "已选：血蚊   1,1 · 3,4"
    assert helpers.texts_of(helpers.find_item(window, "floorMonPos")) == ["1,1 +1"]

    helpers.click_item(window, helpers.find_item(window, "floorMonSelect"))
    assert window.property("gridSelected") == ""


def test_clicking_an_item_row_selects_it_too():
    """测什么：资源行也是点行选中（和怪物行一个规矩）；点效果那句话 = 选中 + 展开，
    再点只是收起，不会把选中点掉。"""
    controller, engine, window = _sheet()
    controller._map_history[0]["items"] = [
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    helpers.show_section(window, "item")

    helpers.click_item(window, helpers.find_item(window, "floorItemEffectToggle"))
    assert window.property("gridSelected") == "红宝石"
    assert helpers.find_all(window, "floorItemRow")[0].property("expanded") is True

    helpers.click_item(window, helpers.find_item(window, "floorItemEffectToggle"))
    assert window.property("gridSelected") == "红宝石"
    assert helpers.find_all(window, "floorItemRow")[0].property("expanded") is False


def test_selected_strip_copy_button_copies_floor_and_cells(monkeypatch):
    """测什么：「已选」条上的「复制」把「名字 层 坐标」放进剪贴板，格式同旧的位置复制。"""
    board = helpers.fake_clipboard(monkeypatch)
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    row = helpers.find_all(window, "floorMonRow")[0]
    helpers.drop_cells(window, row, {"row": 0, "col": 0})
    helpers.click_item(window, helpers.find_item(window, "floorMonSelect"))

    helpers.click_item(window, helpers.find_item(window, "floorSelectedCopy"))

    assert board.value == "血蚊 1层 1,1"


def test_unmarked_entry_strip_says_not_marked_and_has_no_copy_button():
    """测什么：选了一条还没标过位置的词条 → 条上写「还没标位置」，没有复制键。"""
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    helpers.click_item(window, helpers.find_item(window, "floorMonSelect"))

    assert helpers.find_item(window, "floorSelectedText").property("text") \
        == "已选：血蚊   还没标位置"
    assert not helpers.find_item(window, "floorSelectedCopy").isVisible()


def test_menu_toggles_grid_edit_mode():
    """测什么：标位置开关在「⋯」菜单里；标题的「标位置中」徽标跟着它。

    交互顺序：① 开清单（自动在标位置，徽标亮）② 点「⋯」→「退出标位置」→ 徽标灭、
    `gridEditOn` 为假 ③ 再点「⋯」→「进入标位置」→ 又亮。
    """
    controller, engine, window = _sheet()
    assert helpers.find_item(window, "floorEditBadge").isVisible()

    helpers.open_sheet_menu(window)
    helpers.click_item(window, helpers.find_item(window, "floorGridToggle"))
    assert window.property("gridEditOn") is False
    assert not helpers.find_item(window, "floorEditBadge").isVisible()

    helpers.open_sheet_menu(window)
    helpers.click_item(window, helpers.find_item(window, "floorGridToggle"))
    assert window.property("gridEditOn") is True
    assert helpers.find_item(window, "floorEditBadge").isVisible()




# ---- 右下角那个拉大小的把手 ----

def _drag(sheet, item, dx, dy):
    """在这个控件上按下 → 往 (dx, dy) 拖 → 松手（真鼠标事件）。"""
    start = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    end = QPointF(start.x() + dx, start.y() + dy)
    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseButtonPress, start,
                                             start, Qt.LeftButton,
                                             Qt.LeftButton, Qt.NoModifier))
    helpers.APP.processEvents()
    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseMove, end, start,
                                             Qt.NoButton, Qt.LeftButton,
                                             Qt.NoModifier))
    helpers.APP.processEvents()
    helpers.APP.sendEvent(sheet, QMouseEvent(QEvent.MouseButtonRelease, end,
                                             end, Qt.LeftButton, Qt.NoButton,
                                             Qt.NoModifier))
    helpers.APP.processEvents()


def test_resize_grip_grows_the_sheet():
    """测什么：拖右下角的把手 → 窗变大，而且新尺寸记到这一层上（下次开还这么大）。

    交互顺序：① 点「清单 ›」开这一层 ② 按住右下角把手往右下拖 (60, 40) 松手
    → 断言宽高都变大、`floorSizes["长安1"]` 记下新宽度。
    """
    controller, engine, window = _sheet()
    sheet = window.floorSheetOf("长安1")
    grip = sheet.findChildren(QObject, "floorGrip")[0]     # 右下角
    before = (sheet.width(), sheet.height())

    _drag(sheet, grip, 60, 40)

    after = (sheet.width(), sheet.height())
    assert after[0] > before[0], "往右下拖宽度应该变大"
    assert after[1] > before[1], "往右下拖高度应该变大"
    sizes = window.property("floorSizes")
    sizes = sizes.toVariant() if hasattr(sizes, "toVariant") else sizes
    assert int(sizes["长安1"]["w"]) == after[0]


# ---- 楼梯方向开关、拖拽高亮、资源行展开 ----

def test_stair_row_has_thumbnail_and_only_coordinates_and_swaps_direction():
    """测什么：楼梯行 = 缩略图 + 「本层位置 → 出口」，没有别的字（不写上楼/下楼、通到、没标）；
    缩略图不可点；「⇅」才改方向，缩略图跟着换。

    交互顺序：① 开清单（一条上楼）② 缩略图在、行里没有「通到」「没标」③ 点缩略图 →
    方向不变 ④ 点「⇅」→ 变 down、缩略图图片换了 ⑤ 再点 → 变回 up。
    """
    controller, engine, window = _sheet(floors=["长安1", "长安2"])
    controller.addStair("长安1", "up")
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()

    assert helpers.find_item(window, "floorStairThumb") is not None
    row = helpers.find_all(window, "floorStairRow")[0]
    words = "".join(helpers.texts_of(row))
    for junk in ("通到", "没标", "上楼", "下楼", "层"):
        assert junk not in words, "楼梯行里不该有「%s」" % junk
    up_image = str(helpers.find_item(window, "floorStairThumbImage")
                   .property("source"))

    helpers.click_item(window, helpers.find_item(window, "floorStairThumb"))
    assert controller.stairsOf("长安1")[0]["dir"] == "up", "点缩略图不该改方向"

    helpers.click_item(window, helpers.find_item(window, "floorStairDirSwap"))
    helpers.APP.processEvents()
    assert controller.stairsOf("长安1")[0]["dir"] == "down"
    assert str(helpers.find_item(window, "floorStairThumbImage")
               .property("source")) != up_image, "方向变了，缩略图没换"

    helpers.click_item(window, helpers.find_item(window, "floorStairDirSwap"))
    helpers.APP.processEvents()
    assert controller.stairsOf("长安1")[0]["dir"] == "up"


def test_stair_section_has_separate_up_and_down_add_buttons():
    """测什么：楼梯段标题右边有「＋ 上楼」「＋ 下楼」两个按钮，各加一条对应方向的楼梯。"""
    controller, engine, window = _sheet()

    helpers.click_item(window, helpers.find_item(window, "floorAddStairDown"))
    helpers.click_item(window, helpers.find_item(window, "floorAddStair"))
    helpers.APP.processEvents()

    assert [s["dir"] for s in controller.stairsOf("长安1")] == ["down", "up"]
    assert len(helpers.find_all(window, "floorStairRow")) == 2


def test_dragged_cell_over_a_row_lights_it_up_with_drop_here():
    """测什么：拖着格子经过的那一行，胶囊写「放到这里」（整行变淡蓝）；移开恢复。

    `dropKey` 是窗口轮询光标得出的"光标底下是哪一行"，这里直接给它赋值模拟。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    sheet = window.floorSheetOf("长安1")
    assert helpers.texts_of(helpers.find_item(window, "floorMonPos")) == ["未标"]

    sheet.setProperty("dropKey", "monster:0")
    helpers.APP.processEvents()
    assert helpers.texts_of(helpers.find_item(window, "floorMonPos")) == ["放到这里"]

    sheet.setProperty("dropKey", "")
    helpers.APP.processEvents()
    assert helpers.texts_of(helpers.find_item(window, "floorMonPos")) == ["未标"]


def test_rows_in_a_folded_section_do_not_accept_drops():
    """测什么：`rowAt`（地图松手时问"光标底下是哪一行"）不认折起来的段里的行。

    交互顺序：① 开清单（1 只怪 + 1 个资源）② 问怪那一行的中心点 → 是 monster:0
    ③ 折起「怪物」段，再问**同一个点** → 不能还认成 monster:0。
    """
    controller, engine, window = _sheet(mons=[{"name": "血蚊", "count": 1}])
    controller._map_history[0]["items"] = [
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    sheet = window.floorSheetOf("长安1")

    mon_row = helpers.find_all(window, "floorMonRow")[0]
    point = mon_row.mapToScene(QPointF(mon_row.width() / 2,
                                       mon_row.height() / 2))
    spot = sheet.mapToGlobal(point.toPoint())

    def hit():
        found = sheet.rowAt(spot.x(), spot.y())
        found = found.toVariant() if hasattr(found, "toVariant") else found
        return (found["kind"], found["index"]) if found else None

    assert hit() == ("monster", 0)
    helpers.click_item(window, helpers.find_item(window, "floorSecMonToggle"))
    assert hit() != ("monster", 0)


def test_item_effect_line_expands_into_number_boxes():
    """测什么：资源行默认一行写完效果；点这一行才展开数值框，再点收起。"""
    controller, engine, window = _sheet()
    controller._map_history[0]["items"] = [
        {"name": "红宝石", "effect": "攻击力 +1", "count": 1, "icon": "gem_red"}]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()
    helpers.show_section(window, "item")
    row = helpers.find_all(window, "floorItemRow")[0]
    folded = row.height()
    assert helpers.find_item(window, "floorItemEffectLine").property("text") \
        == "攻击力 +1"
    assert row.property("expanded") is False

    helpers.click_item(window, helpers.find_item(window, "floorItemEffectToggle"))
    row = helpers.find_all(window, "floorItemRow")[0]
    assert row.property("expanded") is True
    assert row.height() > folded

    helpers.click_item(window, helpers.find_item(window, "floorItemEffectToggle"))
    row = helpers.find_all(window, "floorItemRow")[0]
    assert row.property("expanded") is False
    assert row.height() == folded
