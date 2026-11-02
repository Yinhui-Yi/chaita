"""用户自己写的技能介绍（logs/skill_notes.json）：`{技能名: 文字}`。

规则：内置的常见技能介绍（assets/skill_effects.json，游戏手册原话）是**只读的底**；
用户在技能介绍卡里写的（不在内置表里的技能）或改写的（不同的魔塔数值可能不同）存在这里，
**优先于内置的**。删掉一条就等于恢复原话。
"""

import json
import os

from ..constants import SKILL_NOTES_PATH
from .state import _ui_state_enabled


def _load_skill_notes() -> dict:
    """读用户写的介绍；没有/坏了都当空。测试里（关了状态文件）也是空。"""
    if not _ui_state_enabled():
        return {}
    try:
        with open(SKILL_NOTES_PATH, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(name).strip(): str(text).strip()
            for name, text in data.items()
            if str(name).strip() and str(text).strip()}


def _save_skill_notes(notes: dict) -> None:
    """写回（先写临时文件再替换，别写出半个 JSON）。测试里是空操作。"""
    if not _ui_state_enabled():
        return
    try:
        folder = os.path.dirname(SKILL_NOTES_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temp = SKILL_NOTES_PATH + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(notes, handle, ensure_ascii=False, indent=2)
        os.replace(temp, SKILL_NOTES_PATH)
    except Exception:
        pass
