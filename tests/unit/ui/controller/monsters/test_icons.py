"""图标单元测试（`chaita/ui/controller/monsters/icons.py`）。

真值来自规则：加资源候选只留图还在的（图没了就不列）。
"""

from unittest.mock import Mock

from chaita.ui.controller.monsters.icons import IconsMixin


class Fake(IconsMixin):
    def __init__(self, history=None):
        self._map_history = history or []
        self.mapHistoryChanged = Mock()


def test_item_choices_filters_missing_icons(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "choices", lambda: [
        {"name": "红宝石", "icon": "gem_red", "effect": "攻击力 +1"},
        {"name": "坏图", "icon": "gone", "effect": ""},
    ])
    monkeypatch.setattr(ii, "icon_exists", lambda stem: stem == "gem_red")
    c = Fake()
    out = c.itemChoices()
    assert [row["name"] for row in out] == ["红宝石"]
