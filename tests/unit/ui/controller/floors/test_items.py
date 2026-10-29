"""这一层资源字段编辑单元测试（`chaita/ui/controller/floors/items.py`）。"""

from unittest.mock import Mock

from chaita.ui.controller.floors.items import ItemsMixin


class Fake(ItemsMixin):
    def __init__(self, history):
        self._map_history = history
        self.mapHistoryChanged = Mock()

    def _find_floor(self, floor_text):
        for index, entry in enumerate(self._map_history):
            if entry.get("floor") == floor_text:
                return index
        return -1

    def _mark_saved(self, *args, **kwargs):
        pass


def make():
    return Fake([{"floor": "1层", "items": [
        {"name": "红血瓶", "icon": "potion_red", "effect": "体力 +150",
         "count": 3}]}])


def test_save_item_count():
    c = make()
    c.saveItemField("1层", 0, "count", "8")
    assert c._map_history[0]["items"][0]["count"] == 8


def test_save_item_effect_marks_manual():
    c = make()
    c.saveItemField("1层", 0, "effect", "体力 +999")
    item = c._map_history[0]["items"][0]
    assert item["effect"] == "体力 +999"
    assert item["effect_manual"] is True


def test_clear_item_name_deletes():
    c = make()
    c.saveItemField("1层", 0, "name", "")
    assert c._map_history[0]["items"] == []


def test_save_item_name_reloads_icon_and_effect(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for",
                        lambda name: "potion_yellow" if "黄" in name
                        else "potion_red")
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "体力 +200")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = make()
    c.saveItemField("1层", 0, "name", "黄血瓶")
    item = c._map_history[0]["items"][0]
    assert item["name"] == "黄血瓶"
    assert item["icon"] == "potion_yellow"
    assert item["effect"] == "体力 +200"   # 没手改过 → 跟着表走


def test_remove_item():
    c = make()
    c.removeItem("1层", 0)
    assert c._map_history[0]["items"] == []


def test_toggle_item_done():
    c = make()
    c.toggleFloorItemDone("1层", 0)
    assert c._map_history[0]["items"][0]["done"] is True
    c.toggleFloorItemDone("1层", 0)
    assert c._map_history[0]["items"][0]["done"] is False


# ---- 新增一条资源 ----

def test_add_item_full_saves_icon_and_effect(monkeypatch):
    import chaita.game.iteminfo as ii
    saved = []
    monkeypatch.setattr(ii, "icon_exists", lambda stem: True)
    monkeypatch.setattr(ii, "save_icon_map",
                        lambda name, stem: saved.append((name, stem)))
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "攻击力 +1")
    monkeypatch.setattr(ii, "icon_for", lambda name: "gem_purple")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = Fake([{"floor": "1层", "items": []}])

    index = c.addItemFull("1层", "红宝石", "", "2", "gem_red")

    assert index == 0
    row = c._map_history[0]["items"][0]
    assert row == {"name": "红宝石", "effect": "攻击力 +1", "count": 2,
                   "icon": "gem_red"}
    assert saved == [("红宝石", "gem_red")]      # 顺手记住"这个名字用这张图"


def test_add_item_full_falls_back_when_icon_save_fails(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_exists", lambda stem: True)
    monkeypatch.setattr(ii, "save_icon_map",
                        lambda name, stem: (_ for _ in ()).throw(OSError("只读")))
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "")
    monkeypatch.setattr(ii, "icon_for", lambda name: "gem_green")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = Fake([{"floor": "1层", "items": []}])

    c.addItemFull("1层", "绿宝石", "", "", "gem_green")

    # 图存不下去也不能炸：退回"按名字查图"
    assert c._map_history[0]["items"][0]["icon"] == "gem_green"


def test_add_item_full_without_icon_uses_table(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_exists", lambda stem: True)
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "体力 +150")
    monkeypatch.setattr(ii, "icon_for", lambda name: "potion_red")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = Fake([{"floor": "1层", "items": []}])

    c.addItemFull("1层", "血瓶", "", "x", "")

    row = c._map_history[0]["items"][0]
    assert row["icon"] == "potion_red"
    assert row["count"] is None                  # 数量不是数字就留空


def test_add_item_full_rejects_blank_name_and_unknown_floor(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_exists", lambda stem: True)
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "")
    monkeypatch.setattr(ii, "icon_for", lambda name: "")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = Fake([{"floor": "1层", "items": []}])

    assert c.addItemFull("1层", "  ", "", "1", "") == -1
    assert c.addItemFull("没有这层", "红宝石", "", "1", "") == -1
    assert c._map_history[0]["items"] == []


# ---- 换种类 ----

def test_set_item_kind_replaces_name_icon_effect(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "攻击力 +0")
    monkeypatch.setattr(ii, "icon_for", lambda name: "h5_sword1")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = make()
    c._map_history[0]["items"][0]["effect_manual"] = True

    c.setItemKind("1层", 0, "铁剑", "", "")

    row = c._map_history[0]["items"][0]
    assert (row["name"], row["icon"], row["effect"]) == \
        ("铁剑", "h5_sword1", "攻击力 +0")
    assert "effect_manual" not in row            # 换了种类，手改标记作废


def test_set_item_kind_keeps_passed_effect_when_table_has_none(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "")
    monkeypatch.setattr(ii, "icon_for", lambda name: "")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = make()

    c.setItemKind("1层", 0, "黄钥匙", "h5_yellowKey", "可以打开一扇黄门")

    assert c._map_history[0]["items"][0]["effect"] == "可以打开一扇黄门"


def test_set_item_kind_ignores_bad_input(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "")
    monkeypatch.setattr(ii, "icon_for", lambda name: "")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = make()
    before = [dict(row) for row in c._map_history[0]["items"]]

    c.setItemKind("1层", 5, "铁剑", "", "")      # 下标越界
    c.setItemKind("1层", 0, "  ", "", "")        # 名字空
    c.setItemKind("没有这层", 0, "铁剑", "", "")

    assert c._map_history[0]["items"] == before


# ---- 字段编辑的边角 ----

def test_save_item_name_keeps_manual_effect(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "icon_for", lambda name: "potion_yellow")
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "体力 +200")
    monkeypatch.setattr(ii, "sort_items", lambda items: items)
    c = make()
    c._map_history[0]["items"][0]["effect_manual"] = True
    c._map_history[0]["items"][0]["effect"] = "体力 +999"

    c.saveItemField("1层", 0, "name", "黄血瓶")

    assert c._map_history[0]["items"][0]["effect"] == "体力 +999"   # 不覆盖手改的


def test_save_item_effect_cleared_drops_manual_flag():
    c = make()
    c.saveItemField("1层", 0, "effect", "体力 +999")
    c.saveItemField("1层", 0, "effect", "")

    assert "effect_manual" not in c._map_history[0]["items"][0]


def test_save_item_count_garbage_clears_it():
    c = make()
    c.saveItemField("1层", 0, "count", "abc")
    assert c._map_history[0]["items"][0]["count"] is None


def test_save_item_field_ignores_bad_input():
    c = make()
    before = [dict(row) for row in c._map_history[0]["items"]]

    c.saveItemField("1层", 9, "count", "1")
    c.saveItemField("1层", 0, "kind", "x")
    c.saveItemField("没有这层", 0, "count", "1")

    assert c._map_history[0]["items"] == before


def test_remove_item_ignores_bad_input():
    c = make()
    c.removeItem("1层", 9)
    c.removeItem("没有这层", 0)
    assert len(c._map_history[0]["items"]) == 1


def test_toggle_done_ignores_bad_input():
    c = make()
    c.toggleFloorItemDone("1层", 9)
    c.toggleFloorItemDone("没有这层", 0)
    assert not c._map_history[0]["items"][0].get("done")


# ---- 效果的拆分/拼接（界面只认这几口 ----

def test_item_effect_parts_and_join():
    c = make()
    assert c.itemEffectLabel("攻击力 +2") == "攻击力"
    assert c.itemEffectValue("攻击力 +2") == "+2"
    assert c.itemEffectJoin("攻击力", "99") == "攻击力 +99"
    assert c.itemEffectParts("攻击力 +2") == {
        "label": "攻击力", "sign": "+", "digits": "2"}
    # 没有数值的效果（钥匙那种）
    assert c.itemEffectValue("可以打开一扇黄门") == ""


def test_item_effect_part_list_and_with_part():
    c = make()
    parts = c.itemEffectPartList("攻击力 +1 · 防御力 +1 · 魔防 +2")
    assert [p["label"] for p in parts] == ["攻击力", "防御力", "魔防"]
    assert c.itemEffectWithPart("攻击力 +1 · 防御力 +1 · 魔防 +2", 1, "5") \
        == "攻击力 +1 · 防御力 +5 · 魔防 +2"


def test_save_item_effect_value_keeps_label():
    c = make()
    c.saveItemEffectValue("1层", 0, "777")

    row = c._map_history[0]["items"][0]
    assert row["effect"] == "体力 +777"          # 属性那半截不动，只换数字
    assert row["effect_manual"] is True


def test_save_item_effect_value_uses_table_label_when_empty(monkeypatch):
    import chaita.game.iteminfo as ii
    monkeypatch.setattr(ii, "effect_for", lambda icon, name: "攻击力 +1")
    c = Fake([{"floor": "1层", "items": [
        {"name": "红宝石", "icon": "gem_red", "effect": "", "count": 1}]}])

    c.saveItemEffectValue("1层", 0, "3")

    assert c._map_history[0]["items"][0]["effect"] == "攻击力 +3"


def test_save_item_effect_part_value_edits_only_that_part():
    c = make()
    c._map_history[0]["items"][0]["effect"] = "攻击力 +1 · 防御力 +1"

    c.saveItemEffectPartValue("1层", 0, 1, "9")

    assert c._map_history[0]["items"][0]["effect"] == "攻击力 +1 · 防御力 +9"


def test_effect_part_savers_ignore_bad_input():
    c = make()
    before = [dict(row) for row in c._map_history[0]["items"]]
    c.saveItemEffectValue("1层", 9, "1")
    c.saveItemEffectValue("没有这层", 0, "1")
    c.saveItemEffectPartValue("1层", 9, 0, "1")
    c.saveItemEffectPartValue("没有这层", 0, 0, "1")
    assert c._map_history[0]["items"] == before
