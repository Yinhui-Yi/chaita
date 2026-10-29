"""routes 的清洗函数 + grid 编辑单元测试。

真值来自规则：一格只留一样、数量跟着位置走、字段白名单、技能只留三样。
"""

from unittest.mock import Mock

from chaita.ui.controller.floors.grid import GridMixin
from chaita.ui.controller.floors.routes import _clean_cells, _clean_fill


def test_clean_cells_keeps_int_coords_only():
    assert _clean_cells([
        {"row": "1", "col": "2"},
        {"row": "x", "col": "y"},
        "不是 dict",
    ]) == [{"row": 1, "col": 2}]


def test_clean_fill_drops_unknown_fields():
    fill = _clean_fill({"kind": "monster", "name": "血蚊", "hp": 100,
                        "atk": 25, "def": 5, "count": 3, "rank": "不该留",
                        "empty": ""})
    assert fill == {"kind": "monster", "name": "血蚊", "hp": 100,
                    "atk": 25, "def": 5, "count": 3}


def test_clean_fill_unknown_kind_is_empty():
    assert _clean_fill({"kind": "npc", "name": "x"}) == {}
    assert _clean_fill("不是 dict") == {}


def test_clean_fill_skills_stripped_to_three_fields():
    fill = _clean_fill({"kind": "monster", "name": "甲",
                        "skills": [{"name": "破甲", "code": "7",
                                    "params": {"defValue": "50"},
                                    "schema": [{"field": "defValue"}]}]})
    assert fill["skills"] == [{"name": "破甲", "code": "7",
                               "params": {"defValue": "50"}}]


class FakeGrid(GridMixin):
    """只带 GridMixin 需要的三样：_map_history、_find_floor、mapHistoryChanged。"""

    def __init__(self, history):
        self._map_history = history
        self.mapHistoryChanged = Mock()

    def _find_floor(self, floor_text):
        for index, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                return index
        return -1


def make(floor="1层", mons=None, grid=None):
    return FakeGrid([{"floor": floor, "mons": mons or [], "items": [],
                      "grid": grid or {}}])


def test_assign_grid_cell_adds_and_syncs_count():
    c = make(mons=[{"name": "血蚊", "count": 3}])
    assert c.assignGridCell("1层", 2, 3, "monster", "血蚊")
    assert c._map_history[0]["grid"]["cells"] == [
        {"row": 2, "col": 3, "kind": "monster", "name": "血蚊"}]
    # 数量跟着位置走：3 → 1
    assert c._map_history[0]["mons"][0]["count"] == 1


def test_assign_grid_cell_replaces_and_resyncs_both():
    c = make(mons=[{"name": "血蚊", "count": 1}, {"name": "铁卫", "count": 1}],
             grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                              "name": "血蚊"}]})
    c.assignGridCell("1层", 0, 0, "monster", "铁卫")
    assert c._map_history[0]["grid"]["cells"] == [
        {"row": 0, "col": 0, "kind": "monster", "name": "铁卫"}]
    mons = {m["name"]: m["count"] for m in c._map_history[0]["mons"]}
    assert mons == {"血蚊": 0, "铁卫": 1}


def test_assign_grid_cell_clears():
    c = make(mons=[{"name": "血蚊", "count": 1}],
             grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                              "name": "血蚊"}]})
    c.assignGridCell("1层", 0, 0, "", "")
    assert c._map_history[0]["grid"]["cells"] == []
    assert c._map_history[0]["mons"][0]["count"] == 0


def test_grid_positions():
    c = make(grid={"cells": [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 2, "col": 3, "kind": "monster", "name": "血蚊"}]})
    assert c.gridPositions("1层", "血蚊") == [{"row": 0, "col": 0},
                                              {"row": 2, "col": 3}]
    assert c.gridPositions("1层", "铁卫") == []


# ---- 一批坐标（Ctrl 多选）----

def test_assign_grid_cells_lands_all_and_signals_once():
    c = make(mons=[{"name": "血蚊", "count": 0}])
    assert c.assignGridCells("1层", [{"row": 0, "col": 0},
                                     {"row": 0, "col": 1},
                                     {"row": 1, "col": 0}], "monster", "血蚊")
    assert [(x["row"], x["col"]) for x in c._map_history[0]["grid"]["cells"]] == [
        (0, 0), (0, 1), (1, 0)]
    assert c._map_history[0]["mons"][0]["count"] == 3
    # 只发一次信号：一格一发会让持有拖放区的词条行在循环中途被重建，
    # 后面的格子读成空名字又被当成"清掉"（用户："编辑模式多选添加有问题"）
    assert c.mapHistoryChanged.emit.call_count == 1


def test_assign_grid_cells_steals_from_other_monster():
    c = make(mons=[{"name": "血蚊", "count": 2}, {"name": "铁卫", "count": 0}],
             grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                              "name": "血蚊"},
                             {"row": 5, "col": 5, "kind": "monster",
                              "name": "血蚊"}]})
    c.assignGridCells("1层", [{"row": 0, "col": 0}, {"row": 1, "col": 1}],
                      "monster", "铁卫")
    mons = {m["name"]: m["count"] for m in c._map_history[0]["mons"]}
    assert mons == {"血蚊": 1, "铁卫": 2}


def test_assign_grid_cells_empty_name_clears_them_all():
    c = make(mons=[{"name": "血蚊", "count": 2}],
             grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                              "name": "血蚊"},
                             {"row": 0, "col": 1, "kind": "monster",
                              "name": "血蚊"}]})
    assert c.assignGridCells("1层", [{"row": 0, "col": 0},
                                     {"row": 0, "col": 1}], "", "")
    assert c._map_history[0]["grid"]["cells"] == []
    assert c._map_history[0]["mons"][0]["count"] == 0


def test_assign_grid_cells_ignores_bad_coords_and_duplicates():
    c = make()
    assert c.assignGridCells("1层", [{"row": 0, "col": 0},
                                     {"row": 0, "col": 0},
                                     {"row": "x", "col": 1},
                                     "不是 dict"], "monster", "血蚊")
    assert c._map_history[0]["grid"]["cells"] == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]


def test_assign_grid_cells_with_no_cells_does_nothing():
    c = make(mons=[{"name": "血蚊", "count": 2}])
    assert c.assignGridCells("1层", [], "monster", "血蚊") is False
    assert c._map_history[0]["mons"][0]["count"] == 2
    assert c.mapHistoryChanged.emit.call_count == 0


def test_assign_grid_cell_is_one_call_of_the_batch():
    c = make(mons=[{"name": "血蚊", "count": 0}])
    c.assignGridCell("1层", 2, 3, "monster", "血蚊")
    assert c._map_history[0]["grid"]["cells"] == [
        {"row": 2, "col": 3, "kind": "monster", "name": "血蚊"}]
    assert c.mapHistoryChanged.emit.call_count == 1


# ---- 13×13 之外不算格子 ----

def test_assign_grid_cells_ignores_out_of_range_targets():
    """第 21 行这种坐标不落格（用户："你怎么选出21，6的"）。"""
    c = make(mons=[{"name": "血蚊", "count": 0}])
    assert c.assignGridCells("1层", [{"row": 20, "col": 5},
                                     {"row": 0, "col": 0}],
                             "monster", "血蚊")
    assert c._map_history[0]["grid"]["cells"] == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]
    assert c._map_history[0]["mons"][0]["count"] == 1


def test_assign_grid_cells_only_out_of_range_does_nothing():
    c = make(mons=[{"name": "血蚊", "count": 2}])
    assert c.assignGridCells("1层", [{"row": 20, "col": 5}],
                             "monster", "血蚊") is False
    assert c.mapHistoryChanged.emit.call_count == 0


def test_assign_grid_cells_drops_stored_out_of_range_cells():
    """存储里已有的脏格（以前拖出来的 20,5）在任意一次落格时自愈。"""
    c = make(mons=[{"name": "血蚊", "count": 2}],
             grid={"cells": [{"row": 0, "col": 0, "kind": "monster",
                              "name": "血蚊"},
                             {"row": 20, "col": 5, "kind": "monster",
                              "name": "血蚊"}]})
    c.assignGridCells("1层", [{"row": 1, "col": 1}], "monster", "血蚊")
    assert c._map_history[0]["grid"]["cells"] == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 1, "col": 1, "kind": "monster", "name": "血蚊"}]
    # 数量按"图上看得到的格"算：2 格
    assert c._map_history[0]["mons"][0]["count"] == 2


def test_grid_positions_and_cells_skip_out_of_range():
    c = make(grid={"cells": [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"},
        {"row": 20, "col": 5, "kind": "monster", "name": "血蚊"}]})
    assert c.gridPositions("1层", "血蚊") == [{"row": 0, "col": 0}]
    assert c.gridCells("1层") == [
        {"row": 0, "col": 0, "kind": "monster", "name": "血蚊"}]
