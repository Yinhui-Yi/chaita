"""读取全链路集成测试：点「读取」→ 后台线程 → 抓图/问模型（stub 最外层）→ 落库。

真值从规则手推：读到层数建记录、怪名归一到手册写法、状态面板按序号写、任务收尾。
抓图/模型/缩略图落盘这三处是边界，用 stub；Controller、_deliver、名字对齐、任务队列
都是真的。
"""

import numpy as np

from chaita.game import capture as cap
from chaita.game import read as game_read
from chaita.game import towers

from .... import helpers


def test_read_game_end_to_end(monkeypatch):
    controller, engine, window = helpers.make_controller()
    # 后台线程改成同步跑（不真开线程），否则要等线程调度
    controller._start_thread = lambda target, args=(): target(*args)
    # 边界 1：抓图/找目标
    monkeypatch.setattr(cap, "find_target",
                        lambda towers_dict, fg: towers.H5_MOTA)
    img = np.zeros((40, 40, 3), np.uint8)
    monkeypatch.setattr(cap, "grab", lambda process: img)
    # 边界 2：模型
    monkeypatch.setattr(game_read, "classify",
                        lambda image, api_key=None: "map")
    monkeypatch.setattr(game_read, "map_snapshot", lambda tower, image: None)
    monkeypatch.setattr(game_read, "grab_window", lambda process: img)

    def fake_read(target, api_key=None, image=None, screen=None,
                  on_floor=None, known=None):
        return game_read.Reading(
            status={"hp": "1000", "atk": "90", "def": "30", "mdef": "10",
                    "floor": "1"},
            map=img, name="新新魔塔", kind="status",
            monsters=[{"name": "血蚊", "count": 2}], floor="1",
            items=[{"name": "红宝石", "effect": "攻击力 +1", "count": 1,
                    "icon": "gem_red"}],
            grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                             "name": "血蚊"}]})

    monkeypatch.setattr(game_read, "read", fake_read)
    # 边界 3：缩略图/原图落盘 + api key
    import chaita.ui.controller.reading.tasks as tasks
    monkeypatch.setattr(tasks, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_save_thumb", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_api_key", lambda: "test-key")

    controller.readGame()
    helpers.APP.processEvents()

    # 落库：这一层建好、怪按手册写法（这里无缩写，原样）、状态面板写了
    entry = controller._map_history[0]
    assert entry["floor"] == "1"
    assert entry["mons"] == [{"name": "血蚊", "count": 2}]
    assert entry["items"][0]["name"] == "红宝石"
    assert controller._last_status["hp"] == "1000"
    assert controller._tower_label == "新新魔塔"
    # 任务收尾：跑完、不卡在"读取中"
    assert controller._tasks[0]["state"] == "done"
    assert controller._active == 0
    assert controller._reading is False


def test_read_monster_manual_wrong_screen_reports(monkeypatch):
    controller, engine, window = helpers.make_controller()
    controller._start_thread = lambda target, args=(): target(*args)
    monkeypatch.setattr(cap, "find_target",
                        lambda towers_dict, fg: towers.H5_MOTA)
    img = np.zeros((40, 40, 3), np.uint8)
    monkeypatch.setattr(cap, "grab", lambda process: img)
    # 画面是地图，却点了「读怪物」→ 该报"现在不是怪物手册"
    monkeypatch.setattr(game_read, "classify",
                        lambda image, api_key=None: "map")
    import chaita.ui.controller.reading.tasks as tasks
    monkeypatch.setattr(tasks, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_save_thumb", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_api_key", lambda: "test-key")

    controller.readOnly("monsters")
    helpers.APP.processEvents()

    assert controller._tasks[0]["state"] == "failed"
    assert "不是怪物手册" in controller._tasks[0]["text"]
    # 没读到东西就不该建层
    assert controller._map_history == []


def test_read_monster_manual_positive(monkeypatch):
    controller, engine, window = helpers.make_controller()
    controller._start_thread = lambda target, args=(): target(*args)
    monkeypatch.setattr(cap, "find_target",
                        lambda towers_dict, fg: towers.H5_MOTA)
    img = np.zeros((40, 40, 3), np.uint8)
    monkeypatch.setattr(cap, "grab", lambda process: img)
    monkeypatch.setattr(game_read, "classify",
                        lambda image, api_key=None: "manual")
    monkeypatch.setattr(game_read, "map_snapshot", lambda tower, image: None)
    monkeypatch.setattr(game_read, "grab_window", lambda process: img)

    def fake_read(target, api_key=None, image=None, screen=None,
                  on_floor=None, known=None):
        return game_read.Reading(
            status={}, map=img, name="新新魔塔", kind="monsters",
            monsters=[{"name": "血蚊", "hp": "1200", "atk": "60", "def": "20",
                       "skills": "先攻", "count": None, "icon": None}])

    monkeypatch.setattr(game_read, "read", fake_read)
    import chaita.ui.controller.reading.tasks as tasks
    monkeypatch.setattr(tasks, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_save_thumb", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_api_key", lambda: "test-key")

    controller.readOnly("monsters")
    helpers.APP.processEvents()

    # 手册读到怪 → _deliver_monsters 落进怪物列表，任务 done
    assert controller._monsters[0]["name"] == "血蚊"
    assert controller._monsters[0]["hp"] == "1200"
    assert controller._tasks[0]["state"] == "done"
    # 读手册只动怪物，不动地图
    assert controller._map_history == []


def test_read_map_only_positive(monkeypatch):
    controller, engine, window = helpers.make_controller()
    controller._start_thread = lambda target, args=(): target(*args)
    monkeypatch.setattr(cap, "find_target",
                        lambda towers_dict, fg: towers.H5_MOTA)
    img = np.zeros((40, 40, 3), np.uint8)
    monkeypatch.setattr(cap, "grab", lambda process: img)
    monkeypatch.setattr(game_read, "classify",
                        lambda image, api_key=None: "map")
    monkeypatch.setattr(game_read, "read_floor",
                        lambda image, api_key=None: "1")
    monkeypatch.setattr(game_read, "map_snapshot", lambda tower, image: None)
    monkeypatch.setattr(game_read, "grab_window", lambda process: img)
    import chaita.ui.controller.reading.tasks as tasks
    monkeypatch.setattr(tasks, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_save_thumb", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_api_key", lambda: "test-key")

    controller._last_status = {"hp": "1000"}   # 读地图不该动状态
    controller.readOnly("map")
    helpers.APP.processEvents()

    # 只读地图：建层记录、塔名更新，但状态面板一个字段都不动
    assert controller._map_history[0]["floor"] == "1"
    assert controller._tower_label == "h5mota 魔塔"
    assert controller._last_status == {"hp": "1000"}
