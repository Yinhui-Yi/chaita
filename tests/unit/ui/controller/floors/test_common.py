"""这一摊共用的小工具单元测试（`chaita/ui/controller/floors/common.py`）。

真值来自规则：**素材名不是文件**（别当"图丢了"）、file:// 和绝对路径才去查磁盘；
地图格子里的**怪名**要按手册写法归一，资源名不动。
"""

import os

import chaita.ui.controller.floors.common as common


# ---- 图标文件还在不在 ----

def test_dead_icon_empty_and_texture_name(monkeypatch):
    monkeypatch.setattr(common.os.path, "exists",
                        lambda p: (_ for _ in ()).throw(
                            AssertionError("不该去查磁盘")))
    assert common._dead_icon_file("") is False
    assert common._dead_icon_file("   ") is False
    # 素材名（potion_red）不是文件：交给 QML 拼 assets/items
    assert common._dead_icon_file("potion_red") is False


def test_dead_icon_absolute_path(monkeypatch):
    seen = []
    monkeypatch.setattr(common.os.path, "isabs", lambda p: True)
    monkeypatch.setattr(common.os.path, "exists",
                        lambda p: seen.append(p) or False)
    assert common._dead_icon_file("C:/temp/a.png") is True
    assert seen == ["C:/temp/a.png"]

    monkeypatch.setattr(common.os.path, "exists", lambda p: True)
    assert common._dead_icon_file("C:/temp/a.png") is False


def test_dead_icon_file_url(monkeypatch):
    import PySide6.QtCore as qtcore
    seen = []

    class FakeUrl:
        def __init__(self, value):
            self.value = value

        def toLocalFile(self):
            return "C:/temp/b.png"

    monkeypatch.setattr(qtcore, "QUrl", FakeUrl)
    monkeypatch.setattr(common.os.path, "exists",
                        lambda p: seen.append(p) or True)

    assert common._dead_icon_file("file:///C:/temp/b.png") is False
    assert seen and seen[0].endswith("b.png")


# ---- 格子里的怪名归一 ----

def test_align_grid_names_rewrites_monster_only(monkeypatch):
    from chaita.game import monster_names
    monkeypatch.setattr(monster_names, "align",
                        lambda names, known: ({"红眼白猫": "红头怪"}, [], []))

    grid = {"cells": [
        {"row": 0, "col": 0, "kind": "monster", "name": "红眼白猫"},
        {"row": 0, "col": 1, "kind": "item", "name": "红眼白猫"},
        {"row": 0, "col": 2, "kind": "monster", "name": ""},
        "不是 dict"]}

    out = common._align_grid_names(grid, [{"name": "红头怪"}])

    assert out["cells"][0]["name"] == "红头怪"      # 怪名归一到手册写法
    assert out["cells"][1]["name"] == "红眼白猫"    # 资源名不动
    assert out["cells"][2]["name"] == ""
    assert len(out["cells"]) == 3                   # 坏条目丢掉
    assert grid["cells"][0]["name"] == "红眼白猫"   # 不改原数据


def test_align_grid_names_without_handbook_returns_copy():
    grid = {"cells": [{"row": 0, "col": 0, "kind": "monster",
                       "name": "红眼白猫"}]}
    out = common._align_grid_names(grid, [])
    assert out["cells"][0]["name"] == "红眼白猫"
    assert out is not grid


def test_align_grid_names_ignores_blank_handbook_names():
    grid = {"cells": [{"row": 0, "col": 0, "kind": "monster", "name": "甲"}]}
    out = common._align_grid_names(grid, [{"name": "  "}, "不是 dict"])
    assert out["cells"][0]["name"] == "甲"
