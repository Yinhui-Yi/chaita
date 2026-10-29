"""skillinfo 单元测试（`chaita/game/skillinfo.py`）。

真值来自 `assets/skill_effects.json`（塔引擎 `getSpecials()` 抽出来的表）。
"""

from chaita.game import skillinfo


def test_code_for():
    assert skillinfo.code_for("破甲") == "7"
    assert skillinfo.code_for("先攻") == "1"
    assert skillinfo.code_for("反击") == "8"
    assert skillinfo.code_for("不存在") == ""


def test_effect_for():
    assert skillinfo.effect_for("破甲").startswith("战斗前，怪物附加角色防御")
    assert skillinfo.effect_for("不存在") == ""


def test_known():
    assert skillinfo.known("破甲")
    assert not skillinfo.known("纳魔为攻")


def test_params_for_armor_break():
    # 破甲的数值参数：field 是引擎里的 defValue
    params = skillinfo.params_for("破甲")
    fields = [p["field"] for p in params]
    assert "defValue" in fields
