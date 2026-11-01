"""会话恢复 / 忽略的**集成测试**（真点横幅上的按钮）。

真值从规则手推：恢复时把层/怪读进列表、地图上模型起的缩写要对到手册真名；
忽略时清提示并删掉那个存档文件。

标准见 `tests/integration/README.md`。驱动：点主界面横幅上的「恢复」/「忽略」。
起点数据（上次退出存下来的那份 `_session`）直接摆；"存档文件怎么来的"（真的退出
进程时写的那一步）不在本文件内。

**改掉的**：原来两条都是直接调 `controller.restoreSession() / discardSession()`
（Slot 直调，一次界面都没经过），现在改成点按钮。
"""

from ... import helpers


def test_restore_button_aligns_the_map_abbreviation():
    """测什么：点「恢复」→ 上次的怪/层回到界面，地图上的缩写被对成手册真名。

    走过的界面：主界面 → 会话横幅「恢复」按钮 → 怪物区 / 地图那一栏的这一层。
    """
    controller, engine, window = helpers.make_controller()
    # _session 是"上次退出存的记录"：手册里有"红色史莱姆"，地图上是缩写"红史莱姆"
    controller._session = {
        "monsters": [{"name": "红色史莱姆"}],
        "floors": [{"floor": "1",
                    "mons": [{"name": "红史莱姆", "count": 2}]}],
    }
    controller._session_hint = "上次的记录：1 层 / 1 只怪"
    controller.sessionHintChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "sessionRestore"))
    helpers.APP.processEvents()

    assert [m["name"] for m in controller.monsters] == ["红色史莱姆"]
    # _align_floor_rows 把地图缩写改成手册真名（monster_names.align 真跑）
    rows = window.sheetMons("1")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else list(rows or [])
    assert rows[0]["name"] == "红色史莱姆"
    assert controller.sessionHint == ""       # 恢复完横幅就没了


def test_discard_button_clears_the_hint_and_removes_the_file(monkeypatch):
    """测什么：点「忽略」→ 横幅消失、存档文件被删掉、不再恢复任何东西。

    走过的界面：主界面 → 会话横幅「忽略」按钮（文件删除用替身拦下来看）。
    """
    import os
    removed = []
    monkeypatch.setattr(os, "remove", lambda p: removed.append(p))
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)

    controller, engine, window = helpers.make_controller()
    controller._session = {"monsters": [{"name": "x"}]}
    controller._session_hint = "1 层 · 1 只怪"
    controller.sessionHintChanged.emit()
    helpers.APP.processEvents()

    helpers.click_item(window, helpers.find_item(window, "sessionDiscard"))
    helpers.APP.processEvents()

    assert controller.sessionHint == ""
    assert len(removed) == 1, "点「忽略」应该把存档文件删掉"
