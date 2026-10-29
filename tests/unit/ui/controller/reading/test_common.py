"""读取共用小函数单元测试（`chaita/ui/controller/reading/common.py`）。

真值来自规则：数量读成 int，读不出来 / 非整数当 0。
"""

import chaita.ui.controller.reading.common as rc


def test_count_of_int():
    assert rc._count_of({"count": 3}) == 3
    assert rc._count_of({"count": "7"}) == 7


def test_count_of_missing_or_invalid_is_zero():
    assert rc._count_of({}) == 0
    assert rc._count_of({"count": None}) == 0
    assert rc._count_of({"count": "x"}) == 0
    assert rc._count_of(None) == 0
