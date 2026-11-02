"""刷新本层单元测试（`chaita/ui/controller/reading/scan.py`）。

真值来自规则（用户 2026-10-31 定的三条）：
  · **清单从格子推**：每格有什么里的东西才进清单，数量 = 它占几格（AI 不读数量）；
  · **没坐标不加行**：这次一个格子都没读到，就什么都不动；
  · **用户手动定过的不要动**：`manual` 的行/格子原样保留，其余按这次读到的重建。
"""

from unittest.mock import Mock

from chaita.ui.controller.floors.records import RecordsMixin
from chaita.ui.controller.reading.scan import ReadingScanMixin


class Fake(ReadingScanMixin, RecordsMixin):
    """两个 mixin 拼起来（真 Controller 就是这么拼的），其余依赖全打成假的。"""

    def __init__(self, history, monsters=None):
        self._map_history = history
        self._monsters = monsters or []
        self.mapHistoryChanged = Mock()
        self.statusTextChanged = Mock()
        self.countingChanged = Mock()
        self._counting_floor = ""
        self._frame = 0
        self.tasks = []

    def _start_thread(self, run):
        self.thread = run

    def _post(self, call):
        call()

    def _set_task(self, task_id, **fields):
        self.tasks.append((task_id, fields))


def _quiet(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def _cell(row, col, kind, name, **extra):
    cell = {"row": row, "col": col, "kind": kind, "name": name}
    cell.update(extra)
    return cell


def _floor(mons=None, items=None, grid=None, memo=None):
    """一层记录；`grid` 传的是**格子列表**（里面按 `{"cells": [...]}` 存）。"""
    entry = {"floor": "1", "mons": mons or [], "items": items or [],
             "grid": {"cells": list(grid or [])}}
    if memo:
        entry["memo"] = memo
    return entry


def _scan(c, grid, task_id=None):
    c._apply_scan("1", {"cells": grid}, task_id=task_id)


# ---- 清单从格子推（数量 = 占几格）----

def test_the_list_comes_from_the_cells_and_the_count_is_the_cell_count(monkeypatch):
    """三格血蚊 + 一格宝石 → 血蚊 3、红宝石 1：数量是数格子数出来的。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor()])

    _scan(c, [_cell(0, 0, "monster", "血蚊"), _cell(0, 1, "monster", "血蚊"),
              _cell(1, 1, "monster", "血蚊"), _cell(2, 2, "item", "红宝石")])

    mons = c._map_history[0]["mons"]
    assert mons == [{"name": "血蚊", "count": 3}]
    assert [i["name"] for i in c._map_history[0]["items"]] == ["红宝石"]
    assert c._map_history[0]["items"][0]["count"] == 1


def test_a_thing_without_a_cell_does_not_get_a_row(monkeypatch):
    """**没坐标不加行**（用户选的 B）：这次只有怪的格子，资源行一条都不该新加。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor()])

    _scan(c, [_cell(0, 0, "monster", "血蚊")])

    assert [i["name"] for i in c._map_history[0]["items"]] == []


def test_no_cells_read_leaves_the_floor_alone(monkeypatch):
    """这次一个格子都没读到 → 清单和坐标都不动（"没读到"不等于"图上没有"）。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor(mons=[{"name": "血蚊", "count": 4}],
                             grid=[_cell(3, 3, "monster", "血蚊")])])
    before = dict(c._map_history[0])

    _scan(c, [])

    assert c._map_history[0] == before


def test_cells_that_are_gone_take_their_ai_rows_with_them(monkeypatch):
    """AI 读进来的行，这次读不到就没了（不然越刷越多）；用户定过的留着。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor(
        mons=[{"name": "血蚊", "count": 1},
              {"name": "铁卫", "count": 2, "manual": True}],
        grid=[_cell(0, 0, "monster", "血蚊"),
              _cell(9, 9, "monster", "铁卫")])])

    _scan(c, [_cell(5, 5, "monster", "青头怪")])

    mons = {row["name"]: row for row in c._map_history[0]["mons"]}
    assert "血蚊" not in mons, "AI 的行这次没读到，应该没"
    assert mons["铁卫"]["count"] == 2, "用户改过的行原样留着"
    assert mons["青头怪"]["count"] == 1


# ---- 用户手动定过的不动 ----

def test_manual_cells_are_kept_and_everything_else_is_read_again(monkeypatch):
    """用户拖的格子留着（同格以用户的为准），AI 的格子按这次的重来（不累计）。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor(grid=[
        _cell(2, 2, "item", "红宝石", effect="攻击力 +1", manual=True),
        _cell(0, 0, "monster", "血蚊")])])

    _scan(c, [_cell(4, 4, "monster", "青头怪"),
              _cell(2, 2, "monster", "血蚊")])       # AI 想占用户那一格

    cells = {(x["row"], x["col"]): x for x in c._map_history[0]["grid"]["cells"]}
    assert cells[(2, 2)]["name"] == "红宝石", "用户标的格子不许被 AI 顶掉"
    assert cells[(2, 2)]["manual"] is True
    assert (0, 0) not in cells, "AI 的旧格子没在这次的读里，应该没"
    assert cells[(4, 4)]["name"] == "青头怪"


def test_manual_rows_keep_their_own_count_and_effect(monkeypatch):
    """用户改过数量的行：格子数变了也不盖掉他的数。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor(
        items=[{"name": "红宝石", "effect": "攻击力 +9", "count": 7,
                "icon": "gem_red", "manual": True}])])

    _scan(c, [_cell(0, 0, "item", "红宝石"), _cell(0, 1, "item", "红宝石")])

    row = c._map_history[0]["items"][0]
    assert row["count"] == 7
    assert row["effect"] == "攻击力 +9"


def test_model_guessed_names_are_aligned_to_the_handbook(monkeypatch):
    """格子里模型猜的简称按手册写法归一（行名和格子名一起改）。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor()], monsters=[{"name": "红色史莱姆"}])

    _scan(c, [_cell(0, 0, "monster", "红史莱姆")])

    assert c._map_history[0]["mons"] == [{"name": "红色史莱姆", "count": 1}]
    assert c._map_history[0]["grid"]["cells"][0]["name"] == "红色史莱姆"


def test_manual_cell_names_are_not_aligned(monkeypatch):
    """用户标的格子连名字都不动（他自己可能就写成那样）。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor(grid=[
        _cell(0, 0, "monster", "红史莱姆", manual=True)])],
        monsters=[{"name": "红色史莱姆"}])

    _scan(c, [_cell(3, 3, "monster", "红史莱姆")])

    cells = {(x["row"], x["col"]): x["name"]
             for x in c._map_history[0]["grid"]["cells"]}
    assert cells[(0, 0)] == "红史莱姆", "用户标的那格名字不动"
    assert cells[(3, 3)] == "红色史莱姆", "AI 的格子归一"


# ---- 资源：同一样东西只留一行，效果和格子对上 ----

def test_same_item_under_two_names_is_one_row(monkeypatch):
    """红药水 / 红血瓶 是同一瓶（按图标身份）：一行、两格。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor()])

    _scan(c, [_cell(0, 0, "item", "红药水"), _cell(0, 1, "item", "红血瓶")])

    items = c._map_history[0]["items"]
    assert len(items) == 1
    assert items[0]["count"] == 2


def test_item_cells_carry_the_row_effect_so_positions_match(monkeypatch):
    """格子也写上这一行的效果：不然 `gridPositions` 认不出"这一行标在哪几格"。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor()])
    # 用道具表的真名（红血瓶 → 体力 +150）
    _scan(c, [_cell(0, 0, "item", "红血瓶")])

    row = c._map_history[0]["items"][0]
    cell = c._map_history[0]["grid"]["cells"][0]
    assert row["effect"], "行上应该有效果（按道具表补的）"
    assert cell["effect"] == row["effect"]


# ---- 楼梯 ----

def test_stairs_are_merged_and_manual_ones_survive(monkeypatch):
    """AI 读到楼梯：用户定过的那行留着，其余按这次读到的来。"""
    _quiet(monkeypatch)
    c = Fake(history=[_floor(grid=[])])
    c._map_history[0]["stairs"] = [{"row": -1, "col": -1, "dir": "up",
                                    "to": "通天塔9", "manual": True}]

    _scan(c, [_cell(0, 6, "stair_up", "上楼梯")])

    stairs = c._map_history[0]["stairs"]
    assert [s.get("to") for s in stairs] == ["通天塔9", ""]
    assert (stairs[1]["row"], stairs[1]["col"]) == (0, 6)


def test_monster_names_that_are_not_in_the_handbook_are_dropped(monkeypatch):
    """手册里已经有名字：格子里对不上任何手册名的怪不记（"哪里来的绿头怪"）。

    用户标的格子不动 —— 他自己标的就归他。
    """
    _quiet(monkeypatch)
    c = Fake(history=[_floor(grid=[
        _cell(0, 0, "monster", "绿头怪", manual=True)])],
        monsters=[{"name": "红色史莱姆"}])

    _scan(c, [_cell(1, 1, "monster", "绿头怪"),
              _cell(2, 2, "monster", "红色史莱姆")])

    names = [(x["row"], x["col"], x["name"])
             for x in c._map_history[0]["grid"]["cells"]]
    assert (0, 0, "绿头怪") in names, "用户标的那格不许被筛掉"
    assert (1, 1, "绿头怪") not in names, "AI 猜的名字对不上手册，不记"
    # 清单从格子里数：用户那一格还在，所以它照样有一行；AI 那一格没进
    assert c._map_history[0]["mons"] == [
        {"name": "绿头怪", "count": 1}, {"name": "红色史莱姆", "count": 1}]


# ---- 任务行 ----

def test_task_text_counts_cells_and_rows(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[_floor()])

    _scan(c, [_cell(0, 0, "monster", "血蚊"),
              _cell(0, 1, "item", "红宝石")], task_id=7)

    text = c.tasks[-1][1]["text"]
    assert text == "1：2 格 · 怪 1 种 · 资源 1 种"
    assert c.tasks[-1][1]["state"] == "done"


def test_apply_scan_reports_missing_floor(monkeypatch):
    _quiet(monkeypatch)
    c = Fake(history=[_floor()])
    c._map_history[0]["floor"] = "2"

    _scan(c, [_cell(0, 0, "monster", "血蚊")], task_id=7)

    assert c.tasks[-1] == (7, {"state": "failed",
                               "text": "统计失败：这层不见了"})


# ---- 刷新任务的整条路：截图读不出来 / 没认出格子 / 认出来了 ----

def _asset(name):
    """仓库里现成的一张图（测试里不写文件，直接借 assets）。"""
    import os
    import chaita
    root = os.path.dirname(os.path.dirname(os.path.abspath(chaita.__file__)))
    return os.path.join(root, "assets", "items", name)


def _run_scan(monkeypatch, image_url, read_floor_map=None):
    import chaita.game.read as game_read
    if read_floor_map is not None:
        monkeypatch.setattr(game_read, "read_floor_map", read_floor_map)
    c = Fake(history=[_floor()], monsters=[{"name": "血蚊"}])
    c._start_scan_task(image_url, "1", task_id=7)
    c.thread()                                  # 同步跑一遍"后台"
    return c


def test_scan_task_sets_counting_while_running(monkeypatch):
    c = Fake(history=[], monsters=[])
    c._start_scan_task("file:///x.png", "1", task_id=7)
    assert c._counting_floor == "1"
    assert c.countingChanged.emit.called
    assert hasattr(c, "thread")


def test_scan_task_reports_unreadable_screenshot(monkeypatch):
    _quiet(monkeypatch)
    c = _run_scan(monkeypatch, "file:///根本没有这个文件.png")

    assert c.tasks[-1] == (7, {"state": "failed",
                               "text": "统计失败：截图读不出来"})
    assert c._counting_floor == ""              # 收尾要把"正在统计"清掉


def test_scan_task_reports_non_image_file(monkeypatch):
    _quiet(monkeypatch)
    import os
    c = _run_scan(monkeypatch, os.path.join(os.path.dirname(_asset("x")),
                                            "..", "..", "pytest.ini"))

    assert c.tasks[-1][1]["text"] == "统计失败：截图读不出来"


def test_scan_task_reports_when_no_cell_was_recognized(monkeypatch):
    """模型挂了 / 没认出格子：任务报失败，记录不动。"""
    _quiet(monkeypatch)
    png = _asset("gem_red.png")

    def boom(*args, **kwargs):
        raise RuntimeError("模型挂了")

    c = _run_scan(monkeypatch, png, read_floor_map=boom)

    assert c.tasks[-1][1]["text"] == "统计失败：没认出格子"


def test_scan_task_applies_what_it_read(monkeypatch):
    _quiet(monkeypatch)
    png = _asset("gem_red.png")

    data = {"mons": [], "items": [],
            "grid": {"cells": [_cell(0, 0, "monster", "血蚊"),
                               _cell(1, 1, "monster", "血蚊"),
                               _cell(2, 2, "item", "红宝石")]}}

    c = _run_scan(monkeypatch, png, read_floor_map=lambda *a, **k: data)

    assert c._map_history[0]["mons"] == [{"name": "血蚊", "count": 2}]
    assert [i["name"] for i in c._map_history[0]["items"]] == ["红宝石"]
    assert c.tasks[-1][1]["state"] == "done"
