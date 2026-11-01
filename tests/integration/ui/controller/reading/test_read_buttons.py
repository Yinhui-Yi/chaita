"""「读地图」「读怪物手册」两个按钮的接线（**集成测试**，真点击）。

`test_read_chain.py` 直接调 `controller.readOnly(...)`，**按钮到 Slot 这一跳没人跑过**：
点错按钮、`readMode` 传错模式、读地图顺手改了状态面板，都是它测不到的。

边界（README 的规矩）：抓图 / 模型 / 缩略图落盘是桩；按钮、`readMode`、任务队列、
`_deliver` 落库、怪名归一都是真的。

起点数据（手册里已有的怪物）直接摆；断言读公开属性（`controller.mapHistory / tasks /
monsters / statusData / chatReply`）。

**删掉的 1 条**：`test_read_pipeline.py` 的两条 —— 它们直接调 `controller._deliver(...)`
这个私有方法，没有经过任何界面。其中"名字归一 → 层记录"那条已经并进本文件的
`test_read_map_button_builds_floor_record`（加了缩写要对到手册真名的断言），
"没读出层数不建层"那条并进 `test_read_map_without_floor_reports_and_stores_nothing`。
"""

import numpy as np

from chaita.game import capture as cap
from chaita.game import read as game_read
from chaita.game import towers

from .... import helpers


def _window(monkeypatch, kind, read_result, floor="3"):
    """起真 Controller + QML，把边界（抓图/模型/落盘）换成桩。"""
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
                        lambda image, api_key=None: floor)
    monkeypatch.setattr(game_read, "read", read_result)
    import chaita.ui.controller.reading.tasks as tasks
    monkeypatch.setattr(tasks, "_save_temp", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_save_thumb", lambda *a, **k: "")
    monkeypatch.setattr(tasks, "_api_key", lambda: "test-key")
    helpers.APP.processEvents()
    return controller, engine, window


def test_read_map_button_builds_floor_record(monkeypatch):
    """测什么：点「读地图」→ 建出这一层的记录，任务 done，状态面板没被动。

    交互顺序：① 主界面地图那一栏点「读取」（读地图）→（桩）抓图 + 模型 →
    ② 断言层记录出现、任务 done、状态面板一个字没改。

    （"模型起的缩写要归一到手册真名"这条走的是 `_deliver`，在单测
    `tests/unit/ui/controller/reading/test_deliver.py::test_deliver_monsters_aligns_floor_abbreviation`
    里覆盖；那条集成用例直接调私有 `_deliver`，不算集成，已经删了。）
    """
    img = np.zeros((40, 40, 3), np.uint8)

    def fake_read(target, api_key=None, image=None, screen=None,
                  on_floor=None, known=None):
        return game_read.Reading(
            status={"hp": "1000"}, map=img, name="新新魔塔", kind="map",
            monsters=[], floor="3", items=[],
            grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                             "name": "红史莱姆"}]})

    controller, engine, window = _window(monkeypatch, "map", fake_read)
    controller._last_status = {"hp": "1000"}
    controller.statusTextChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "readMap"))
    helpers.APP.processEvents()

    entry = controller.mapHistory[0]
    assert entry["floor"] == "3"
    assert controller.tasks[0]["state"] == "done"
    # 任务收尾：不卡在"读取中"（按钮上那个状态就是读这两处）
    assert controller.reading is False
    assert controller.activeReads == 0
    # 读地图不该动状态面板
    assert dict(controller.statusData) == {"hp": "1000"}


def test_read_monster_button_fills_manual(monkeypatch):
    """测什么：点「读怪物手册」→ 怪物手册里多一只；不建地图层。

    交互顺序：① 点怪物那栏的「读取」（读手册）→（桩）抓图 + 模型 →
    ② 断言库里多出这只怪、层记录还是空的。
    """
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

    assert controller.monsters[0]["name"] == "血蚊"
    assert controller.monsters[0]["hp"] == "1200"
    # 读手册只动怪物，不建地图层
    assert list(controller.mapHistory) == []


def test_read_monster_button_wrong_screen_reports(monkeypatch):
    """测什么：画面是地图却点了「读怪物」→ 任务失败并说清"现在不是怪物手册"，不静默。

    交互顺序：① 点怪物那栏的「读取」→（桩）分类结果说这是地图 →
    ② 断言任务 failed、文案说明画面不对，且模型根本没被调用。
    """

    def fake_read(*args, **kwargs):        # 不该被调到
        raise AssertionError("画面不是手册时不该去读")

    controller, engine, window = _window(monkeypatch, "map", fake_read)

    helpers.click_item(window, helpers.find_item(window, "readMon"))
    helpers.APP.processEvents()

    task = controller.tasks[0]
    assert task["state"] == "failed"
    assert "不是怪物手册" in task["text"]


def test_read_map_without_floor_reports_and_stores_nothing(monkeypatch):
    """测什么：模型没读出层数 → 不建层记录，并在对话里说一句"没读出层数"。

    交互顺序：① 点「读地图」→（桩）模型返回 floor=None →
    ② 断言没有层记录、`chatReply` 里说明没读出层数。
    """
    img = np.zeros((40, 40, 3), np.uint8)

    def fake_read(target, api_key=None, image=None, screen=None,
                  on_floor=None, known=None):
        return game_read.Reading(
            status={"hp": "1000"}, map=None, name="新新魔塔", kind="status",
            monsters=[], floor=None, items=[])

    controller, engine, window = _window(monkeypatch, "map", fake_read,
                                         floor=None)

    helpers.click_item(window, helpers.find_item(window, "readMap"))
    helpers.APP.processEvents()

    assert list(controller.mapHistory) == []
    assert "没读出层数" in controller.chatReply
