"""楼梯单元测试：一层有好几个、每个自己记得通哪层、老写法自动转换。

真值来自规则（用户 2026-10-30 两次纠正）：
- 一层可以有**好几个**上下楼（不是固定两个）；
- 通哪一层写在这一行上（`to`），跟层号顺序无关；
- 坐标 13×13 以内，-1 = 还没标位置；
- 老记录 `{"up": {...}, "down": {...}}` 读的时候要自动变成列表。
"""

from unittest.mock import Mock

from chaita.ui.controller.floors.stairs import StairsMixin, _stairs_list


class FakeStairs(StairsMixin):
    def __init__(self, history):
        self._map_history = history
        self.mapHistoryChanged = Mock()

    def _find_floor(self, floor_text):
        for index, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                return index
        return -1


def make(floor="0层", stairs=None, other=None):
    history = [{"floor": floor, "mons": [], "items": [], "grid": {}}]
    if stairs is not None:
        history[0]["stairs"] = stairs
    if other:
        history.extend(other)
    return FakeStairs(history)


def test_old_two_key_format_becomes_a_list():
    """老记录（一层两个 key）自动转成列表，不丢。"""
    assert _stairs_list({"up": {"row": 1, "col": 2},
                         "down": {"row": 5, "col": 6}}) == [
        {"row": 1, "col": 2, "dir": "up", "to": "",
         "toRow": -1, "toCol": -1},
        {"row": 5, "col": 6, "dir": "down", "to": "",
         "toRow": -1, "toCol": -1}]
    assert _stairs_list(None) == []
    assert _stairs_list("不是 list") == []


def test_a_floor_can_have_several_stairs_and_each_has_its_own_target():
    c = make()
    first = c.addStair("0层", "up")
    second = c.addStair("0层", "up")
    third = c.addStair("0层", "down")
    assert (first, second, third) == (0, 1, 2)
    assert c.saveStair("0层", 0, 2, 3)
    assert c.saveStair("0层", 1, 9, 10)
    assert c.saveStair("0层", 2, 12, 1)
    # 同一层两个上楼梯去不同的层（用户："谁告诉你0层就一定去1层的"）
    assert c.setStairTarget("0层", 0, "1层")
    assert c.setStairTarget("0层", 1, "5层")
    assert [(one["row"], one["col"], one["dir"], one["to"])
            for one in c.stairsOf("0层")] == [
        (2, 3, "up", "1层"), (9, 10, "up", "5层"), (12, 1, "down", "")]


def test_new_stair_has_no_position_and_no_target_yet():
    c = make()
    assert c.addStair("0层") == 0
    assert c.stairsOf("0层") == [{"row": -1, "col": -1, "dir": "up",
                                  "to": "", "toRow": -1, "toCol": -1}]


def test_save_stair_rejects_bad_input():
    c = make(stairs=[{"row": -1, "col": -1, "dir": "up", "to": ""}])
    assert c.saveStair("0层", 0, 13, 0) is False
    assert c.saveStair("0层", 9, 1, 1) is False
    assert c.saveStair("没有这层", 0, 1, 1) is False
    assert c.stairsOf("0层") == [{"row": -1, "col": -1, "dir": "up",
                                  "to": "", "toRow": -1, "toCol": -1}]


def test_remove_stair_takes_out_one_row():
    c = make(stairs=[{"row": 1, "col": 1, "dir": "up", "to": "1层"},
                     {"row": 2, "col": 2, "dir": "up", "to": "5层"}])
    assert c.removeStair("0层", 0)
    assert [(one["row"], one["col"], one["to"])
            for one in c.stairsOf("0层")] == [(2, 2, "5层")]
    assert c.removeStair("0层", 0)
    # 全删掉之后记录里不留空列表
    assert "stairs" not in c._map_history[0]


def test_set_target_needs_a_valid_row():
    c = make(stairs=[{"row": 1, "col": 1, "dir": "up", "to": ""}])
    assert c.setStairTarget("0层", 0, "7层") is True
    assert c.stairsOf("0层")[0]["to"] == "7层"
    assert c.setStairTarget("0层", 3, "7层") is False


def test_direction_can_be_fixed_after_the_fact():
    """AI 把上/下认错了：点一下缩略图就该换过来（方向不改位置和目标层）。"""
    c = make(stairs=[{"row": 2, "col": 3, "dir": "up", "to": "1层"}])
    assert c.setStairDirection("0层", 0, "down") is True
    assert [(one["dir"], one["to"], one["row"], one["col"])
            for one in c.stairsOf("0层")] == [("down", "1层", 2, 3)]
    assert c.setStairDirection("0层", 0, "sideways") is False
    assert c.setStairDirection("0层", 5, "up") is False


def test_add_down_stair_keeps_its_direction():
    """「＋ 下楼梯」加出来的那行就是下楼梯。"""
    c = make()
    assert c.addStair("0层", "down") == 0
    assert c.stairsOf("0层")[0]["dir"] == "down"
