"""技能的效果说明（玩游戏的人看的那句话）。

数据来源是**塔自己的引擎**：h5mota 的 `project/functions.js` 里
`enemys.getSpecials()` 那张表就是游戏在怪物手册上显示技能说明用的，
`tools/build_skill_effects.py` 把它抽成 `assets/skill_effects.json`
（引擎一份 + 用户那两座塔各自的一份，塔的说明优先）。

这里只做查询，不猜、不算：
- 查得到就给游戏里那句原话（动态数字用 … 表示）；
- 查不到（塔自己加的技能，比如"纳魔为攻"）返回空串，界面照实说"以游戏里的手册为准"。
"""

import json
import os
import re

from ..paths import ASSETS as _ASSETS
PATH = os.path.join(_ASSETS, "skill_effects.json")
PARAMS_PATH = os.path.join(_ASSETS, "skill_params.json")

_CACHE = {}
_PARAMS = {}


def _table() -> dict:
    if "data" in _CACHE:
        return _CACHE["data"]
    data = {}
    try:
        with open(PATH, encoding="utf-8-sig") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
    _CACHE["data"] = data
    return data


def _param_table() -> dict:
    """技能的数值参数表（tools/build_skill_params.py 从引擎里抽的）。

    每项 `{field, label, unit, type}`：field 就是引擎里的 `enemy.<字段>`
    （破甲是 defValue、吸血是 value+add……），以后算伤害直接按 code 取。
    """
    if "data" in _PARAMS:
        return _PARAMS["data"]
    data = {}
    try:
        with open(PARAMS_PATH, encoding="utf-8-sig") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
    _PARAMS["data"] = data
    return data


def _names() -> dict:
    by_name = _table().get("by_name")
    return by_name if isinstance(by_name, dict) else {}


def _row_for(name: str):
    text = (name or "").strip()
    if not text:
        return None
    row = _names().get(text)
    if not row:
        # 手册上有时带后缀（"无法战斗[b]"），去掉再试一次
        base = re.sub(r"\[[^\]]*\]\s*$", "", text).strip()
        row = _names().get(base) if base else None
    return row if isinstance(row, dict) else None


def effect_for(name: str) -> str:
    """技能名的效果说明；没有说明返回空串。"""
    row = _row_for(name)
    if not row:
        return ""
    return str(row.get("desc") or "").strip()


def code_for(name: str) -> str:
    """技能名 → 引擎里的 code（"7" = 破甲）。查不到返回空串。"""
    row = _row_for(name)
    if not row:
        return ""
    return str(row.get("code") or "").strip()


def params_for(name: str) -> list:
    """这个技能要填哪几个数（返回表中参数的拷贝，改坏了也不影响缓存）。"""
    code = code_for(name)
    if not code:
        return []
    table = _param_table().get("by_code")
    if not isinstance(table, dict):
        return []
    row = table.get(code)
    if not isinstance(row, dict):
        return []
    out = []
    for item in row.get("params") or []:
        if not isinstance(item, dict) or not item.get("field"):
            continue
        out.append({"field": str(item["field"]),
                    "label": str(item.get("label") or item["field"]),
                    "unit": str(item.get("unit") or ""),
                    "type": str(item.get("type") or "int")})
    return out


def known(name: str) -> bool:
    return bool(effect_for(name))
