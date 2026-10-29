"""「读地图」「读怪物手册」两个按钮的接线（真点击）。

`test_read_chain.py` 直接调 `controller.readOnly(...)`，**按钮到 Slot 这一跳没人跑过**：
点错按钮、`readMode` 传错模式、读地图顺手改了状态面板，都是它测不到的。

抓图 / 模型 / 落盘是边界上的桩；按钮、`readMode`、任务队列、落库都是真的。
"""

import numpy as np

from chaita.game import capture as cap
from chaita.game import read as game_read
from chaita.game import towers

from .... import helpers


def _window(monkeypatch, kind, read_result):
    controller, engine, window = helpers.make_controller()
    controller._start_thread = lambda target, args=(): target(*args)
    monkeypatch.setattr(cap, "find_target",
                        lambda towers_dict, fg: towers.H5_MOTA)
    img = np.zeros((40, 40, 3), np.uint8)
    monkeypatch.setattr(cap, "grab", lambda process: img)
    monkeypatch.setattr(game_read, "classify",
                        lambda image, api_key=None: kind)
    monkeypatch.setattr(game_read, "grab_window", lambda process: img)
    monkeypatch.setattr(game_read, "map_snapshot", lambda tower, image: None)
    monkeypatch.setattr(game_read, "read_floor",
                        lambda image, api_key=None: "3")
    monkeypatch.setattr(game_read, "read", read_result)
    import chaita.ui.controller.reading.tasks as tasks
    monkeypatch.setattr(tasks, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_save_thumb", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_api_key", lambda: "test-key")
    helpers.APP.processEvents()
    return controller, engine, window


def test_read_map_button_builds_floor_record(monkeypatch):
    img = np.zeros((40, 40, 3), np.uint8)

    def fake_read(target, api_key=None, image=None, screen=None,
                  on_floor=None, known=None):
        return game_read.Reading(
            status={"hp": "1000"}, map=img, name="新新魔塔", kind="map",
            monsters=[], floor="3", items=[],
            grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                             "name": "血蚊"}]})

    controller, engine, window = _window(monkeypatch, "map", fake_read)
    controller._last_status = {"hp": "1000"}

    helpers.click_item(window, helpers.find_item(window, "readMap"))
    helpers.APP.processEvents()

    assert controller._map_history[0]["floor"] == "3"
    assert controller._tasks[0]["state"] == "done"
    # 读地图不该动状态面板
    assert controller._last_status == {"hp": "1000"}


def test_read_monster_button_fills_manual(monkeypatch):
    img = np.zeros((40, 40, 3), np.uint8)

    def fake_read(target, api_key=None, image=None, screen=None,
                  on_floor=None, known=None):
        return game_read.Reading(
            status={}, map=img, name="新新魔塔", kind="monsters",
            monsters=[{"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
                       "skills": "先攻", "count": None, "icon": None}])

    controller, engine, window = _window(monkeypatch, "manual", fake_read)

    helpers.click_item(window, helpers.find_item(window, "readMon"))
    helpers.APP.processEvents()

    assert controller._monsters[0]["name"] == "血蚊"
    assert controller._monsters[0]["hp"] == "1200"
    # 读手册只动怪物，不建地图层
    assert controller._map_history == []


def test_read_monster_button_wrong_screen_reports(monkeypatch):
    """画面是地图却点了「读怪物」：要报"现在不是怪物手册"，不静默。"""

    def fake_read(*args, **kwargs):        # 不该被调到
        raise AssertionError("画面不是手册时不该去读")

    controller, engine, window = _window(monkeypatch, "map", fake_read)

    helpers.click_item(window, helpers.find_item(window, "readMon"))
    helpers.APP.processEvents()

    assert controller._tasks[0]["state"] == "failed"
    assert "不是怪物手册" in controller._tasks[0]["text"]
