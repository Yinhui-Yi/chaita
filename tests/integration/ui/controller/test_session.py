"""会话恢复/丢弃链路集成测试（`chaita/ui/controller/session.py`）。

真值从规则手推：恢复时把层/怪读进列表、地图上模型起的缩写对到手册真名；丢弃时清提示并删文件。
"""

from ... import helpers


def test_restore_session_aligns_floor_abbreviation(monkeypatch):
    controller, engine, window = helpers.make_controller()
    # _session 是"上次退出存的记录"：手册里有"红色史莱姆"，地图上是缩写"红史莱姆"
    controller._session = {
        "monsters": [{"name": "红色史莱姆"}],
        "floors": [{"floor": "1",
                    "mons": [{"name": "红史莱姆", "count": 2}]}],
    }
    controller.restoreSession()
    helpers.APP.processEvents()

    assert controller._monsters == [{"name": "红色史莱姆"}]
    # _align_floor_rows 把地图缩写改成手册真名（monster_names.align 真跑）
    assert controller._map_history[0]["mons"][0]["name"] == "红色史莱姆"
    assert controller._session == {}          # 恢复完就清掉


def test_discard_session_clears_hint_and_removes_file(monkeypatch):
    import os
    removed = []
    monkeypatch.setattr(os, "remove", lambda p: removed.append(p))
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)

    controller, engine, window = helpers.make_controller()
    controller._session = {"monsters": [{"name": "x"}]}
    controller._session_hint = "1 层 · 1 只怪"
    controller.discardSession()

    assert controller._session == {}
    assert controller._session_hint == ""
    assert len(removed) == 1
