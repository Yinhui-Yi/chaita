"""从引擎的「特殊属性表」里抽每个技能 code 的**数值参数**（以后算伤害用）。

为什么要有这一步：
手册上"破甲：附加角色防御的 …%作为伤害"里的 … 不是随便一个数字，它在引擎里是
`enemy.defValue`（破甲）、`enemy.value`（吸血/领域/激光）、`enemy.damage`（固伤）……
把数字写进一段自由文本，就等于把"哪个数是什么"丢了；要算伤害必须留着
`code + 具名参数`。

产物：assets/skill_params.json
    {"by_code": {"7": {"name": "破甲", "engine_fields": ["defValue"],
                        "params": [{"field": "defValue", "label": "防御百分比",
                                    "unit": "%", "type": "percent"}]}, ...}}

参数是从引擎 `getSpecials()` 的**描述函数体**里挖出来的（`enemy.xxx`），
标签/单位/控件类型在上面的 LABELS 里定；两边对不上就报错退出，
免得哪天引擎多了一个字段、这里悄悄漏掉。

跑法：
    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\build_skill_params.py
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "skill_params.json")

ENGINE_FILES = [
    r"C:\Users\87790\dev\mt1005-solve\mt1005\project\functions.js",
]

# 每个 code 的参数：字段名要与引擎里 `enemy.<字段>` 一致（这样以后公式能直接对上）
# type: int / percent / toggle / choice
LABELS = {
    "6": [("n", "次数", "次", "int")],
    "7": [("defValue", "防御百分比", "%", "percent")],
    "8": [("atkValue", "攻击百分比", "%", "percent")],
    "9": [("n", "倍数", "倍", "int")],
    "11": [("value", "吸血百分比", "%", "percent"),
           ("add", "伤害加到自身", "", "toggle")],
    "15": [("zoneSquare", "范围", "", "choice"),
           ("range", "格数", "格", "int"),
           ("value", "伤害", "点", "int")],
    "18": [("zoneSquare", "范围", "", "choice"),
           ("value", "伤害", "点", "int")],
    "21": [("atkValue", "攻击下降", "点", "int"),
           ("defValue", "防御下降", "点", "int")],
    "22": [("damage", "固定伤害", "点", "int")],
    "24": [("value", "伤害", "点", "int")],
    "25": [("zoneSquare", "范围", "", "choice"),
           ("range", "格数", "格", "int"),
           ("value", "生命提升", "%", "percent"),
           ("atkValue", "攻击提升", "%", "percent"),
           ("defValue", "防御提升", "%", "percent"),
           ("add", "可叠加", "", "toggle")],
}

# 这些 code 的说明只用全局常量（core.values.xxx），不是"这只怪的"参数
GLOBAL_ONLY = {"12", "13", "17"}


def _get_specials_block(text):
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


def _name_from(entry):
    literals = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', entry)
    for text in literals:
        text = text.replace('\\"', '"').replace("\\\\", "\\").strip()
        if text and len(text) <= 12 and not re.fullmatch(r"[A-Za-z_$][\w$.]*", text):
            return text
    return ""


def _parse(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError:
        return {}
    block = _get_specials_block(text)
    if not block:
        return {}
    out = {}
    for entry in _split_entries(block):
        match = re.match(r"(\d+)", entry[1:].lstrip())
        if not match:
            continue
        code = match.group(1)
        fields = []
        for field in re.findall(r"enemy\.([A-Za-z_]\w*)", entry):
            if field not in fields:
                fields.append(field)
        out[code] = {"name": _name_from(entry), "engine_fields": fields}
    return out


def main():
    codes = {}
    for path in ENGINE_FILES:
        codes.update(_parse(path))
    if not codes:
        print("读不到引擎的 getSpecials（%s）" % ENGINE_FILES[0])
        return 1
    by_code = {}
    problems = []
    for code in sorted(codes, key=int):
        row = codes[code]
        fields = row["engine_fields"]
        curated = LABELS.get(code, [])
        names = [item[0] for item in curated]
        missing = [name for name in names if name not in fields]
        if missing:
            problems.append("%s %s：引擎里没有字段 %s（实际 %s）"
                            % (code, row["name"], missing, fields))
        params = [{"field": field, "label": label, "unit": unit,
                   "type": kind} for field, label, unit, kind in curated]
        by_code[code] = {"name": row["name"],
                         "engine_fields": fields,
                         "params": params}
        if code in GLOBAL_ONLY and fields:
            # 这些说明用了"每只怪的字段"就不能算全局常量：提醒一句，别硬压
            print("注意：code %s 的说明里有 enemy.%s"
                  % (code, ", enemy.".join(fields)))
    if problems:
        for line in problems:
            print("ERROR", line)
        return 1
    data = {"source": "engine getSpecials", "by_code": by_code}
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    total = sum(len(row["params"]) for row in by_code.values())
    with_params = [code for code, row in by_code.items() if row["params"]]
    print("写出 %s：%d 个 code，%d 个参数，%d 个技能带参数"
          % (OUT, len(by_code), total, len(with_params)))
    for code in with_params:
        print("  %-3s %-6s %s" % (code, by_code[code]["name"],
                                  "/".join(p["label"] for p in by_code[code]["params"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
