"""状态区单元测试（`chaita/ui/controller/status.py`）。

真值来自规则：状态拆三段文本、update 只覆盖读到值的字段、空值/下划线字段不动。
"""

from unittest.mock import Mock

from chaita.ui.controller.status import StatusMixin


class _Tower:
    name = "新新魔塔"


class Fake(StatusMixin):
    def __init__(self):
        self._status_text = ""
        self._attr_text = ""
        self._items_text = ""
        self._gold_text = ""
        self._last_status = {}
        self._status_at = ""
        self.statusTextChanged = Mock()
        self._tower_label = ""
        self._last_tower = None


def test_apply_status_splits_three_sections():
    c = Fake()
    c._apply_status({"hp": 1000, "atk": 90, "def": 30, "mdef": 10,
                     "gold": 500})
    assert c._attr_text == "生命 1000   攻击 90   防御 30   魔防 10"
    assert c._gold_text == "金币 500"
    assert c._status_at != ""
    assert c.statusTextChanged.emit.called


def test_apply_person_merges_and_skips_empty():
    c = Fake()
    c._last_status = {"hp": "1000", "atk": "90", "gold": "500"}
    c._apply_person(_Tower(), {"hp": "900", "atk": "", "_raw": "x",
                               "gold": None, "mdef": "10"})
    assert c._last_status["hp"] == "900"
    assert c._last_status["mdef"] == "10"
    assert c._last_status["atk"] == "90"       # 空值不覆盖
    assert c._last_status["gold"] == "500"     # None 不覆盖
    assert "_raw" not in c._last_status        # 下划线字段不动
    assert c._tower_label == "新新魔塔"


def test_apply_person_non_dict_is_noop():
    c = Fake()
    c._last_status = {"hp": "1000"}
    c._apply_person(_Tower(), "not a dict")
    assert c._last_status == {"hp": "1000"}
