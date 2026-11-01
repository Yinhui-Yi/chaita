"""用户技能介绍的读写单元测试（`chaita/ui/toolkit/notes.py`）。

规则：`{技能名: 文字}`；坏文件/空条目当没有；关了状态文件开关（测试环境）既不读也不写。
"""

import json

import chaita.ui.toolkit.notes as notes


def _point_at(monkeypatch, tmp_path):
    path = tmp_path / "skill_notes.json"
    monkeypatch.setattr(notes, "SKILL_NOTES_PATH", str(path))
    monkeypatch.delenv("CHAITA_NO_UI_STATE", raising=False)
    return path


def test_存了再读_原样回来(monkeypatch, tmp_path):
    path = _point_at(monkeypatch, tmp_path)
    notes._save_skill_notes({"破甲": "加角色防御的 40%", "纳魔为攻": "魔防转攻击"})

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "破甲": "加角色防御的 40%", "纳魔为攻": "魔防转攻击"}
    assert notes._load_skill_notes() == {"破甲": "加角色防御的 40%",
                                         "纳魔为攻": "魔防转攻击"}


def test_没有文件_坏文件_不是字典_都当空(monkeypatch, tmp_path):
    path = _point_at(monkeypatch, tmp_path)
    assert notes._load_skill_notes() == {}                  # 没有文件

    path.write_text("{坏了", encoding="utf-8")
    assert notes._load_skill_notes() == {}                  # 坏 JSON

    path.write_text("[1, 2]", encoding="utf-8")
    assert notes._load_skill_notes() == {}                  # 不是字典


def test_读的时候丢掉空名字和空介绍(monkeypatch, tmp_path):
    path = _point_at(monkeypatch, tmp_path)
    path.write_text(json.dumps({"破甲": "  有字  ", "": "无名", "吸血": "   "},
                               ensure_ascii=False), encoding="utf-8")
    assert notes._load_skill_notes() == {"破甲": "有字"}


def test_带BOM的文件也能读(monkeypatch, tmp_path):
    path = _point_at(monkeypatch, tmp_path)
    path.write_text(json.dumps({"破甲": "x"}), encoding="utf-8-sig")
    assert notes._load_skill_notes() == {"破甲": "x"}


def test_关了状态文件开关就不读也不写(monkeypatch, tmp_path):
    path = _point_at(monkeypatch, tmp_path)
    path.write_text(json.dumps({"破甲": "旧"}), encoding="utf-8")
    monkeypatch.setenv("CHAITA_NO_UI_STATE", "1")

    assert notes._load_skill_notes() == {}
    notes._save_skill_notes({"破甲": "新"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"破甲": "旧"}
