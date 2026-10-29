"""主面板的按钮接线（真点击）：会话恢复/忽略、任务取消/重试、怪物行打开编辑并保存。

这些东西以前只有 controller 的 Slot 级单测，QML 那一层（`sessionRestore` 到底调了谁、
`taskRetry` 点的是哪一条任务、怪物行点开的是哪一只、保存写回的是不是那一行）没人跑过。
"""

import numpy as np

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


def test_session_restore_button_restores_saved_session():
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

    assert [m["name"] for m in controller._monsters] == ["血蚊"]
    assert [f["floor"] for f in controller._map_history] == ["1"]
    assert controller._session_hint == ""


def test_session_discard_button_drops_the_file(monkeypatch):
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
    assert controller._session_hint == ""


def test_task_cancel_button_marks_that_task():
    controller, engine, window = _window()
    controller._tasks = [{"id": 7, "seq": 1, "state": "running",
                          "text": "读取中…", "mode": "map", "started": 0}]
    controller.tasksChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "taskCancel"))
    helpers.APP.processEvents()

    assert controller._tasks[0]["state"] == "cancelled"
    assert controller._tasks[0]["text"] == "已取消"


def test_task_retry_button_reads_person_again(monkeypatch):
    """人物的任务没有截图可复用：重试 = 再读一次人物面板。"""
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
    helpers.wait_for(lambda: controller._last_status.get("hp") == "777",
                     timeout=2.0)

    # 那条失败任务被换掉了（重试会新起一条），人物数值按新读到的写
    assert [t["id"] for t in controller._tasks] == [1]
    assert controller._tasks[0]["state"] == "done"
    assert controller._last_status["hp"] == "777"


def test_monster_row_opens_editor_and_save_renames():
    controller, engine, window = _window()
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

    assert controller._monsters[0]["name"] == "血蚊改名"


def test_monster_editor_cancel_keeps_original():
    controller, engine, window = _window()
    before = [dict(m) for m in controller._monsters]

    helpers.click_item(window, helpers.find_all(window, "monOpen")[0])
    helpers.APP.processEvents()
    helpers.click_item(window, helpers.find_item(window, "monCancel"))
    helpers.APP.processEvents()

    assert window.property("monEdit") == -1
    assert controller._monsters == before


# ---- 地图块 / 折叠头 / 行尾 ✕ ----

def _floors(controller, window, floors=("3层",)):
    controller._map_history = [
        {"floor": floor, "url": "", "mons": [], "items": [],
         "grid": {"cells": []}} for floor in floors]
    controller.mapHistoryChanged.emit()
    helpers.APP.processEvents()


def test_map_tile_opens_that_floor_sheet():
    controller, engine, window = _window()
    _floors(controller, window, ["3层", "4层"])

    helpers.click_item(window, helpers.find_all(window, "mapTile")[0])
    helpers.APP.processEvents()

    value = window.property("floorWindows").toVariant()
    assert value == ["3层"]


def test_floor_refresh_button_reports_missing_screenshot():
    controller, engine, window = _window()
    _floors(controller, window)

    helpers.click_item(window, helpers.find_item(window, "mapRefresh"))
    helpers.APP.processEvents()

    task = controller._tasks[0]
    assert task["state"] == "failed"
    assert "还没有地图截图" in task["text"]


def test_section_heads_toggle_collapse():
    controller, engine, window = _window()
    helpers.APP.processEvents()
    assert window.property("mapCollapsed") is False

    helpers.click_item(window, helpers.find_item(window, "mapSectionHead"))
    assert window.property("mapCollapsed") is True
    helpers.click_item(window, helpers.find_item(window, "mapSectionHead"))
    assert window.property("mapCollapsed") is False

    helpers.click_item(window, helpers.find_item(window, "monSectionHead"))
    assert window.property("monCollapsed") is True

    helpers.click_item(window, helpers.find_item(window, "skillSectionHead"))
    assert window.property("skillCollapsed") is True


def test_monster_row_delete_removes_that_monster():
    controller, engine, window = _window()

    helpers.click_item(window, helpers.find_all(window, "monDeleteRow")[0])
    helpers.APP.processEvents()

    assert [m["name"] for m in controller._monsters] == ["铁卫"]


def test_drag_indicator_follows_drag_state():
    """拖到哪一行前面，就在那一行顶上画一条落点线（用户要的"插在这儿"）。"""
    controller, engine, window = _window()
    assert helpers.find_all(window, "monDropLine") == []   # 没在拖 → 一条都没有

    controller.monDragStart(0, 100.0, 20.0, 2)
    controller._mon_drag["to"] = 1                 # 模拟光标落在第 2 行
    controller.monDragChanged.emit()
    helpers.APP.processEvents()

    assert len(helpers.find_all(window, "monDropLine")) == 1

    controller.monDragFinish()
    helpers.APP.processEvents()
    assert helpers.find_all(window, "monDropLine") == []
