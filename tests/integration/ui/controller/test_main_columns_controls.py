"""主面板那几个按钮的接线（**集成测试**，只点界面上有的东西）。

覆盖：会话横幅的「恢复 / 忽略」、读取记录里的「取消 / 重试」、怪物行点开编辑并保存 /
取消、地图那一栏（侧栏切层、大图、底部那句话、清单入口、刷新）、标签条（切页、读取
按钮跟着当前页）、塔名和导航条同一行、怪物库那一行的 ✕。断言一律读**公开属性**（`controller.monsters / mapHistory / tasks /
statusData`、`window` 的属性、界面上的文字），不读 `controller._xxx` 内部字段。

标准见 `tests/integration/README.md`。剪贴板/抓图/模型是外部边界，用替身；
起点数据（怪物库、层记录、任务队列）直接摆，读取链路不在本文件内。

**不符合标准、已经删掉的**：
  · `test_drag_indicator_follows_drag_state` —— 直调 `monDragStart()/monDragChanged.emit()/
    monDragFinish()`，一次鼠标事件都没发；拖拽落点线现在**没有自动化覆盖**
  · 原来的 `test_map_strip_shows_the_selected_floor_only` + `test_map_rail_switches_the_floor`
    两条合并成一条（都用真点击选层，不调 `selectFloor()`）
"""

import numpy as np
from PySide6.QtCore import QPointF

from chaita.game import read as game_read

from ... import helpers


def _window():
    controller, engine, window = helpers.make_controller()
    controller._monsters = [
        {"name": "血蚊", "hp": "1200", "atk": "60", "def": "20"},
        {"name": "铁卫", "hp": "900", "atk": "50", "def": "30"}]
    # 怪物行是缓存属性（`monRows`），要靠信号刷出来，不然界面上根本没有行
    controller.monstersChanged.emit()
    helpers.APP.processEvents()
    return controller, engine, window


def _floors(controller, floors=("3层",)):
    controller._map_history = [
        {"floor": floor, "url": "", "mons": [], "items": [],
         "grid": {"cells": []}, "routes": []} for floor in floors]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()


def _open_map_bar(window):
    """真实用户动作：不在地图页就点一下「地图」标签。"""
    if window.property("tab") != "map":
        helpers.click_item(window, helpers.find_item(window, "tab_map"))
        helpers.APP.processEvents()
    assert helpers.wait_for(
        lambda: helpers.find_item(window, "mapPanel") is not None), \
        "地图那一页没显示"


def test_session_restore_button_restores_the_saved_session():
    """测什么：点横幅上的「恢复」→ 上次那一局回到怪物库和层记录里，横幅消失。

    走过的界面：主界面 → 会话横幅「恢复」按钮 → 怪物区 / 地图那一栏。
    """
    controller, engine, window = _window()
    controller._session = {
        "monsters": [{"name": "血蚊", "hp": "1200"}],
        "floors": [{"floor": "1", "mons": [], "items": [],
                    "grid": {"cells": []}}]}
    controller._session_hint = "上次的记录：1 层 / 1 只怪"
    controller.sessionHintChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "sessionRestore"))
    helpers.APP.processEvents()

    assert [m["name"] for m in controller.monsters] == ["血蚊"]
    assert [f["floor"] for f in controller.mapHistory] == ["1"]
    assert controller.sessionHint == ""


def test_session_discard_button_drops_the_file(monkeypatch):
    """测什么：点「忽略」→ 存档文件被删掉、横幅消失。

    走过的界面：主界面 → 会话横幅「忽略」按钮。
    """
    import chaita.ui.controller.session as session_mod
    removed = []
    monkeypatch.setattr(session_mod.os, "remove",
                        lambda path: removed.append(path))

    controller, engine, window = _window()
    controller._session_hint = "上次的记录：1 层"
    controller.sessionHintChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "sessionDiscard"))
    helpers.APP.processEvents()

    assert removed, "点「忽略」应该把存档文件删掉"
    assert controller.sessionHint == ""


def test_task_cancel_button_marks_that_task():
    """测什么：读取记录里那条跑着的任务，点「取消」→ 这一条变成"已取消"。

    走过的界面：主界面「读取记录」→ 那一条任务的取消按钮。
    """
    controller, engine, window = _window()
    controller._tasks = [{"id": 7, "seq": 1, "state": "running",
                          "text": "读取中…", "mode": "map", "started": 0}]
    controller.tasksChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "taskCancel"))
    helpers.APP.processEvents()

    task = controller.tasks[0]
    assert task["state"] == "cancelled"
    assert task["text"] == "已取消"


def test_task_retry_button_reads_person_again(monkeypatch):
    """测什么：失败的人物任务点「重试」→ 真的再读一次人物面板，任务变成完成。

    走过的界面：主界面「读取记录」→ 失败那条的重试按钮 →（桩）抓图 + 读人物。
    """
    controller, engine, window = _window()
    controller._start_thread = lambda target, args=(): target(*args)
    img = np.zeros((20, 20, 3), np.uint8)
    # 找窗口也得桩掉：真去问 Windows，机器上开没开游戏会决定这条测试的结果
    from chaita.game import towers
    helpers.fake_game_window(monkeypatch, towers.H5_MOTA.process)
    monkeypatch.setattr(game_read, "grab_window", lambda p: img)
    monkeypatch.setattr(game_read, "read_person",
                        lambda image, api_key=None: {"hp": "777"})
    import chaita.ui.controller.status as status_mod
    monkeypatch.setattr(status_mod, "_api_key", lambda: "test-key")

    controller._last_status = {"hp": "1000"}
    controller._tasks = [{"id": 9, "seq": 1, "state": "failed",
                          "text": "读取失败", "mode": "status", "started": 0}]
    controller.tasksChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "taskRetry"))
    # 重试的结果走 uiCall（队列连接）排回界面线程：等它落地再断言
    assert helpers.wait_for(
        lambda: str(controller.statusData.get("hp") or "") == "777",
        timeout=2.0), controller.statusData

    ids = [t["id"] for t in controller.tasks]
    assert 9 not in ids, "旧的失败任务应该被新的那次替换掉"
    assert controller.tasks[0]["state"] == "done"


def test_monster_row_opens_editor_and_save_writes_back():
    """测什么：点怪物库那一行 → 编辑卡片打开 → 改名后点「保存」→ 写回那一只。

    走过的界面：主界面怪物行（点开）→ 编辑卡片（名字输入框）→ 「保存」。
    """
    controller, engine, window = _window()
    helpers.open_tab(window, "monsters")
    helpers.click_item(window, helpers.find_all(window, "monOpen")[0])
    helpers.APP.processEvents()
    assert window.property("monEdit") == 0

    name_field = helpers.find_item(window, "monNameField")
    name_field.forceActiveFocus()
    helpers.APP.processEvents()
    name_field.setProperty("text", "血蚊改名")
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "monSave"))
    helpers.APP.processEvents()

    assert controller.monsters[0]["name"] == "血蚊改名"


def test_monster_editor_cancel_keeps_original():
    """测什么：编辑卡片点「取消」→ 卡片关掉、怪物库一点没变。

    走过的界面：主界面怪物行 → 编辑卡片 → 「取消」。
    """
    controller, engine, window = _window()
    before = [dict(m) for m in controller.monsters]

    helpers.open_tab(window, "monsters")
    helpers.click_item(window, helpers.find_all(window, "monOpen")[0])
    helpers.APP.processEvents()
    helpers.click_item(window, helpers.find_item(window, "monCancel"))
    helpers.APP.processEvents()

    assert window.property("monEdit") == -1
    assert [dict(m) for m in controller.monsters] == before


def test_rail_lists_floors_and_clicking_one_switches_the_big_map():
    """测什么：侧栏一行一层、只写层号；点哪行大图就换哪层，底部那句话跟着这一层。

    走过的界面：主界面 → 地图标题（展开）→ 左侧栏的行 → 大图 + 底部那一条。
    """
    controller, engine, window = _window()
    _floors(controller, ["通天塔3", "通天塔4"])
    _open_map_bar(window)

    rows = helpers.find_all(window, "floorRailRow")
    assert [helpers.texts_of(row)[0] for row in rows] == ["4", "3"]

    helpers.click_item(window, rows[0])               # 上面那行 = 通天塔4
    helpers.APP.processEvents()
    assert window.property("mapFloor") == "通天塔4"
    card = helpers.find_item(window, "mapCard")
    assert card is not None and card.width() > 200
    # 这一层没标楼梯 → 底部直接说「楼梯没标」
    assert str(helpers.find_item(window, "mapFoot").property("text")) == "楼梯没标"

    helpers.click_item(window, helpers.find_all(window, "floorRailRow")[1])
    helpers.APP.processEvents()
    assert window.property("mapFloor") == "通天塔3"


def test_map_sheet_button_opens_the_list_for_that_floor():
    """测什么：点底部「清单 ›」→ 打开这一层那扇小窗，里面有「＋ 加怪 / ＋ 加资源」。

    走过的界面：主界面 → 地图那一栏 →「清单 ›」→「这一层」小窗。
    """
    controller, engine, window = _window()
    _floors(controller, ["通天塔3"])
    _open_map_bar(window)
    helpers.click_item(window, helpers.find_all(window, "floorRailRow")[0])
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("通天塔3") is not None) is True
    assert helpers.find_item(window, "floorAddMon") is not None
    assert helpers.find_item(window, "floorAddItem") is not None


def test_the_list_opened_from_the_map_follows_the_floor():
    """测什么：清单开着的时候在侧栏切层 → 清单跟着换成那一层，位置不跳、旧窗收掉。

    走过的界面：主界面侧栏（点行切层）→「清单 ›」那扇小窗。
    """
    controller, engine, window = _window()
    _floors(controller, ["通天塔3", "通天塔4"])
    _open_map_bar(window)
    helpers.click_item(window, helpers.find_all(window, "floorRailRow")[1])  # 3层
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "mapSheet"))
    assert helpers.wait_for(
        lambda: window.floorSheetOf("通天塔3") is not None) is True
    before = window.floorSheetOf("通天塔3")
    x = before.x()
    y = before.y()

    helpers.click_item(window, helpers.find_all(window, "floorRailRow")[0])   # 4层
    helpers.APP.processEvents()
    assert window.property("mapFloor") == "通天塔4"
    assert helpers.wait_for(
        lambda: window.floorSheetOf("通天塔4") is not None) is True
    after = window.floorSheetOf("通天塔4")
    assert after.property("sheetName") == "通天塔4"
    assert (after.x(), after.y()) == (x, y), "换层时清单不该跳位置"
    assert window.floorSheetOf("通天塔3") is None, "旧那一层的窗应该收掉"


def test_floor_refresh_button_reports_missing_screenshot():
    """测什么：这一层没有截图时点「刷新」→ 读取记录里出现一条失败说明。

    走过的界面：主界面 → 地图那一栏 →「刷新」→ 读取记录。
    """
    controller, engine, window = _window()
    _floors(controller, ["3层"])
    _open_map_bar(window)
    helpers.click_item(window, helpers.find_all(window, "floorRailRow")[0])
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "mapRefresh"))
    helpers.APP.processEvents()

    task = controller.tasks[0]
    assert task["state"] == "failed"
    assert "还没有地图截图" in task["text"]


def test_点标签页切换地图_怪物_技能():
    """测什么：三个标签点一下就切到那一页，一次只有一页的内容可见。

    走过的界面：主界面标签条（地图 / 怪物 / 技能）。
    """
    controller, engine, window = _window()
    helpers.APP.processEvents()
    assert window.property("tab") == "map"

    helpers.click_item(window, helpers.find_item(window, "tab_monsters"))
    helpers.APP.processEvents()
    assert window.property("tab") == "monsters"
    assert all(item.isVisible()
               for item in helpers.find_all(window, "monRow"))

    helpers.click_item(window, helpers.find_item(window, "tab_skills"))
    helpers.APP.processEvents()
    assert window.property("tab") == "skills"
    assert not any(item.isVisible()
                   for item in helpers.find_all(window, "monRow"))

    helpers.click_item(window, helpers.find_item(window, "tab_map"))
    helpers.APP.processEvents()
    assert window.property("tab") == "map"


def test_三个标签页内容区一样高_切页窗口高度不跳():
    """测什么：有地图时，怪物页/技能页的内容区垫到和地图页一样高，切页时窗口不变高变矮。

    走过的界面：主界面标签条切页，量窗口高度。
    """
    controller, engine, window = _window()
    _floors(controller)
    heights = {}
    for tab in ("map", "monsters", "skills"):
        helpers.click_item(window, helpers.find_item(window, "tab_" + tab))
        helpers.APP.processEvents()
        heights[tab] = window.property("expandedHeight")
    assert heights["monsters"] == heights["map"]
    assert heights["skills"] == heights["map"]


def test_读取按钮跟着当前页_技能页没有读取():
    """测什么：地图页只有地图的「读取」，怪物页只有手册的「读取」，技能页一个都没有。

    走过的界面：主界面标签条右上角的「读取」按钮。
    """
    controller, engine, window = _window()
    seen = {}
    for tab in ("map", "monsters", "skills"):
        helpers.open_tab(window, tab)
        seen[tab] = (helpers.find_item(window, "readMap").isVisible(),
                     helpers.find_item(window, "readMon").isVisible())
    assert seen == {"map": (True, False), "monsters": (False, True),
                    "skills": (False, False)}


def test_塔名和导航条在同一行():
    """测什么：塔名画在导航条那一行（和 ✕ 的纵向中心一致），不再单占一行。

    走过的界面：主窗口抬头。
    """
    controller, engine, window = _window()
    controller._tower_label = "拆个魔塔 通天塔1"
    controller.statusTextChanged.emit()
    helpers.APP.processEvents()

    label = helpers.find_item(window, "towerLabel")
    close = helpers.find_item(window, "closeBtn")
    assert label.property("text") == "拆个魔塔 通天塔1"
    centre = lambda item: item.mapToScene(
        QPointF(0, item.height() / 2)).y()
    assert abs(centre(label) - centre(close)) < 1


def test_monster_row_delete_removes_that_monster():
    """测什么：怪物库那一行点 ✕ → 库里少一只，剩下那只不动。

    走过的界面：主界面怪物区的行尾 ✕。
    """
    controller, engine, window = _window()

    helpers.open_tab(window, "monsters")
    helpers.click_item(window, helpers.find_all(window, "monDeleteRow")[0])
    helpers.APP.processEvents()

    assert [m["name"] for m in controller.monsters] == ["铁卫"]
