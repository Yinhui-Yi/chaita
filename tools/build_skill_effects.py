"""把塔的引擎里那份「特殊属性表」抽出来，做成界面能直接显示的效果说明。

为什么要从引擎源码里抽，而不是自己编/让用户填：
h5mota 的 `project/functions.js` 里 `enemys.getSpecials()` 就是**游戏自己**用来
在怪物手册上显示技能说明的那张表（数字, 名字, 描述, 颜色, 标记），
描述很多时候是函数（比如破甲的"附加角色防御的 30%"），这里只取其中的固定文字，
动态数字留给用户自己记的数值。

产物：assets/skill_effects.json
    {"by_code": {"1": {"name": "先攻", "desc": "怪物首先攻击", "source": "mt1005"}},
     "by_name": {"先攻": {"code": "1", "desc": "怪物首先攻击", "source": "mt1005"}}}

by_name 来自 assets/monster_templates.db 的 skill 表（两座塔的实际叫法），
所以「坚固 / 硬化 / 魔攻」这些同码不同名的都能对上说明。

跑法：
    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\build_skill_effects.py
"""

import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "assets", "monster_templates.db")
OUT = os.path.join(ROOT, "assets", "skill_effects.json")

# 引擎源码（这就是"游戏自己怎么描述这个技能"的出处）
ENGINE_FILES = [
    r"C:\Users\87790\dev\mt1005-solve\mt1005\project\functions.js",
]
# 用户的两座塔如果有自己的 getSpecials，说明以塔为准（覆盖同 code 的）
TOWER_FILES = [
    r"C:\Users\87790\Downloads\xinxin\mota_pack_20260623_204744\project\functions.js",
    r"C:\Users\87790\Downloads\xinxin2new\xinxin2\project\functions.js",
]

STRING = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')


def _unescape(text):
    """只处理引号/反斜杠这类转义。

    别用 `encode().decode("unicode_escape")`：那会把 UTF-8 的中文变成
    latin-1 乱码（第一次跑出来就是 "åæ»"）。
    """
    return text.replace('\\"', '"').replace("\\\\", "\\")


def _looks_like_name(text):
    """技能名得像个中文名字：拦掉从函数体里误抓到的 "object" / "function" 之类。"""
    text = (text or "").strip()
    if not text or len(text) > 12:
        return False
    return not re.fullmatch(r"[A-Za-z_$][\w$.]*", text)


def _get_specials_block(text):
    """截出 getSpecials 里 return [ ... ]; 那一段。"""
    at = text.find("getSpecials")
    if at < 0:
        return ""
    start = text.find("return", at)
    if start < 0:
        return ""
    bracket = text.find("[", start)
    if bracket < 0:
        return ""
    depth = 0
    for pos in range(bracket, len(text)):
        char = text[pos]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[bracket:pos + 1]
    return ""


def _split_entries(block):
    """按顶层逗号把 [ [..], [..] ] 拆成一行一条。"""
    entries = []
    depth = 0
    start = None
    for pos, char in enumerate(block):
        if char == "[":
            depth += 1
            if depth == 2 and start is None:
                start = pos
        elif char == "]":
            if depth == 2 and start is not None:
                entries.append(block[start:pos + 1])
                start = None
            depth -= 1
    return entries


def _desc_from(entry):
    """第 3 项：字符串直接用；函数就取里面的固定文字（动态数字留空）。"""
    # 去掉第 1 项的编号
    body = entry[1:-1].strip()
    parts = []
    depth = 0
    text = ""
    quote = None
    for pos, char in enumerate(body):
        if quote:
            text += char
            if char == quote and body[pos - 1] != "\\":
                quote = None
            continue
        if char in "\"'":
            quote = char
            text += char
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        text += char
    # 逗号分层（忽略函数体里的逗号）
    fields = []
    depth = 0
    quote = None
    current = ""
    for pos, char in enumerate(body):
        if quote:
            current += char
            if char == quote and body[pos - 1] != "\\":
                quote = None
            continue
        if char in "\"'":
            quote = char
            current += char
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            fields.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        fields.append(current.strip())
    if len(fields) < 3:
        return ""
    desc = fields[2]
    # 三元表达式是"二选一的两种说法"，不是先后两段文字：
    # `(enemy.zoneSquare ? "九宫格" : "十字")` 直接拼上 … 会读成"周围…九宫格…十字…"。
    # 先换成 "九宫格/十字"，剩下的动态数字才用 … 表示。
    desc = re.sub(
        r'\(\s*[^?()"]+\?\s*"([^"]*)"\s*:\s*"([^"]*)"\s*\)',
        lambda m: '"%s"' % (
            (m.group(1) + "/" + m.group(2)) if (m.group(1) and m.group(2))
            else (m.group(1) or m.group(2))), desc)
    literals = [_unescape(s) for s in STRING.findall(desc)]
    literals = [s for s in literals if s.strip()]
    if not literals:
        return ""
    if len(literals) == 1:
        return literals[0].strip()
    # 多段文字（中间夹着 enemy.value 之类的动态数字）：用 … 表示那一段
    return ("…".join(s.strip() for s in literals)).strip()


def _parse(path, tag):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
    except Exception:
        return {}
    block = _get_specials_block(text)
    if not block:
        return {}
    out = {}
    for entry in _split_entries(block):
        head = entry[1:].lstrip()
        match = re.match(r"(\d+)", head)
        if not match:
            continue
        code = match.group(1)
        desc = _desc_from(entry)
        literals = [_unescape(s) for s in STRING.findall(entry)]
        name = next((s.strip() for s in literals if _looks_like_name(s)), "")
        out[code] = {"name": name, "desc": desc, "source": tag}
    return out


def _db_skills():
    conn = sqlite3.connect(DB)
    try:
        return list(conn.execute("SELECT name, codes FROM skill ORDER BY id"))
    finally:
        conn.close()


def main():
    by_code = {}
    for path in ENGINE_FILES:
        by_code.update(_parse(path, "engine"))
    for path in TOWER_FILES:
        for code, row in _parse(path, "tower").items():
            old = by_code.get(code) or {}
            by_code[code] = {
                # 名字以引擎那份为准（塔里偶尔写成函数，抓出来是 "object"）
                "name": old.get("name") or row.get("name") or "",
                # 说明以塔为准：玩家实际看的是这塔的手册
                "desc": row.get("desc") or old.get("desc") or "",
                "source": "tower" if row.get("desc") else old.get("source", ""),
            }
    if not by_code:
        print("没解析到任何特殊属性表（引擎文件路径变了？）")
        return 1

    by_name = {}
    missing = []
    for name, codes in _db_skills():
        name = (name or "").strip()
        if not name:
            continue
        found = None
        for code in str(codes or "").replace("，", ",").split(","):
            code = code.strip()
            if code in by_code and by_code[code]["desc"]:
                found = (code, by_code[code])
                break
        if found:
            by_name[name] = {"code": found[0], "desc": found[1]["desc"],
                             "source": found[1]["source"]}
        else:
            by_name[name] = {"code": str(codes or ""), "desc": "", "source": ""}
            missing.append(name)

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump({"by_code": by_code, "by_name": by_name}, handle,
                  ensure_ascii=False, indent=1)
    print("特殊属性 %d 条 -> %s" % (len(by_code), os.path.relpath(OUT, ROOT)))
    print("库里的技能 %d 个，有说明的 %d 个"
          % (len(by_name), len(by_name) - len(missing)))
    if missing:
        print("没有说明（塔自己加的，界面显示\"以游戏里手册为准\"）：")
        print("  " + "、".join(missing))
    for code in sorted(by_code, key=lambda c: int(c))[:6]:
        print("  %s %s：%s" % (code, by_code[code]["name"], by_code[code]["desc"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
