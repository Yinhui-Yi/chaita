"""建资源效果表：`assets/item_effects.json`（每个资源图标默认是什么效果）。

用户的原话：「效果还让我填，魔塔里什么道具什么效果你不会看游戏吗？」
—— 效果不该让用户手填。这里从两座塔的 `project/items.js` + `project/data.js`
把"血瓶 / 宝石"的 `itemEffectTip` 解析出来，并把 `core.values.xxx` 换成真实数值，
按**图标**（potion_red / gem_red …）落成一张表；界面加资源时直接带出效果。

注意：不同塔的同一件道具有效效果可能不一样（xinxin 的绿宝石是敏捷+1，
xinxin2 的绿宝石是气息条上限-1）。表里以 xinxin（经典版）为准，
另一座塔的值记在 `alternatives` 里，界面上照填、也能改。

    python tools/build_item_effects.py
    python tools/build_item_effects.py <xinxin目录> <xinxin2目录>
"""

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
OUT_PATH = os.path.join(ASSETS, "item_effects.json")
MAP_PATH = os.path.join(ASSETS, "items", "map.json")

HOME = os.path.expanduser("~")
DEFAULT_TOWERS = [
    os.path.join(HOME, "Downloads", "xinxin", "mota_pack_20260623_204744"),
    os.path.join(HOME, "Downloads", "xinxin2new", "xinxin2"),
]
LABELS = ["rm", "h5"]

# 塔里的 key 前缀颜色 → 我们的图标名
COLORS = {"red": "red", "blue": "purple", "green": "green", "yellow": "yellow"}
KINDS = {"Potion": "potion", "Gem": "gem"}


def read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def objects(text):
    """按括号配平切出 `"key": { ... }`，能容忍函数体里的括号。"""
    out = {}
    for match in re.finditer(r'"([A-Za-z0-9_]+)"\s*:\s*\{', text):
        start = match.end() - 1
        depth = 0
        i = start
        while i < len(text):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out[match.group(1)] = text[start:i + 1]
    return out


def values_of(text):
    match = re.search(r'"values"\s*:\s*\{', text)
    if not match:
        return {}
    start = match.end() - 1
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = text[start:i + 1]
    return {key: int(value) for key, value in
            re.findall(r'"([A-Za-z0-9_]+)"\s*:\s*(-?\d+)', body)}


def expand(tip, values):
    """把 ${'，体力 +'+core.values.redPotion * core.status.thisMap.ratio} 变成 "体力 +150"。"""
    text = tip
    # $ 外面有时还有一层引号/花括号：统一按"取模板里的中文说明 + 数字"处理
    pieces = re.findall(r"'([^']*)'|core\.values\.([A-Za-z0-9_]+)|\+?", text)
    if not pieces:
        return ""
    out = []
    for literal, key in pieces:
        if literal:
            out.append(literal)
        elif key:
            out.append(str(values.get(key, "?")))
    joined = "".join(out)
    joined = joined.replace("，", "").replace("ratio", "").strip()
    joined = re.sub(r"\s+", " ", joined)
    return joined


ATTR_LABELS = (("hp", "生命"), ("atk", "攻击"), ("def", "防御"),
               ("mdef", "魔防"), ("exp", "经验"), ("gold", "金币"))


def expand_attrs(body, values):
    """从 `itemEffect` 语句里读出"每项属性加多少"：core.status.hero.atk += 6。

    为什么要有这条：黄宝石在塔里的 tip 只写「全属性提升」，界面上就这么原样
    显示，等于什么都没说（用户：「把全属性提升改成每一项属性的具体值」）。
    真正的数值在 itemEffect 里，一条一条是明明白白的。
    """
    labels = dict(ATTR_LABELS)
    out = []
    for field, amount in re.findall(
            r"core\.status\.hero\.([A-Za-z]+)\s*\+=\s*([^;；]+)[;；]", body):
        amount = amount.strip()
        if amount.startswith("core.values."):
            amount = str(values.get(amount.split(".")[-1], amount))
        if not re.match(r"^-?\d+$", amount):
            continue
        label = labels.get(field)
        if not label:
            continue
        out.append("%s +%s" % (label, amount))
    return " · ".join(out)


def collect_tower(label, proj):
    items_path = os.path.join(proj, "project", "items.js")
    data_path = os.path.join(proj, "project", "data.js")
    if not os.path.exists(items_path):
        return {}
    items = objects(read(items_path))
    values = values_of(read(data_path)) if os.path.exists(data_path) else {}
    out = {}
    for key, body in items.items():
        match = re.match(r"(red|blue|green|yellow)(Potion|Gem)", key)
        if not match:
            continue
        color = COLORS[match.group(1)]
        kind = KINDS[match.group(2)]
        stem = "%s_%s" % (kind, color)
        name = re.search(r'"name"\s*:\s*"([^"]*)"', body)
        tip = re.search(r'"itemEffectTip"\s*:\s*"([^"]*)"', body)
        effect = expand(tip.group(1), values) if tip else ""
        # 「全属性提升」这类说不清的 tip，换成每项属性的具体数值
        if "全属性" in effect or not effect:
            concrete = expand_attrs(body, values)
            if concrete:
                effect = concrete
        out[stem] = {
            "tower": label,
            "key": key,
            "name": name.group(1) if name else key,
            "effect": effect,
        }
    return out


def main() -> int:
    towers = DEFAULT_TOWERS
    if len(sys.argv) > 2:
        towers = sys.argv[1:3]
    collected = {}
    for label, proj in zip(LABELS, towers):
        if not os.path.isdir(proj):
            print("跳过（不存在）：%s" % proj)
            continue
        for stem, entry in collect_tower(label, proj).items():
            bucket = collected.setdefault(stem, {})
            bucket[label] = entry

    if not collected:
        print("两座塔都没读到 items.js，退出")
        return 1

    # 我们自己的资源名 → 图标（assets/items/map.json），用来给每个图标选一个展示名
    try:
        mapping = json.load(io.open(MAP_PATH, encoding="utf-8"))
    except Exception:
        mapping = {}
    names_by_stem = {}
    for name, stem in mapping.items():
        names_by_stem.setdefault(stem, []).append(name)

    def pick_name(stem, default):
        names = names_by_stem.get(stem) or []
        # 优先"血瓶/宝石"这种正规叫法（map.json 里 红药水 和 红血瓶 指向同一张图）
        for preferred in ("血瓶", "宝石"):
            for name in names:
                if preferred in name:
                    return name
        return names[0] if names else default

    table = {}
    for stem, per_tower in sorted(collected.items()):
        primary = per_tower.get(LABELS[0]) or next(iter(per_tower.values()))
        alternatives = [entry["effect"] for label, entry in per_tower.items()
                        if label != primary["tower"] and entry.get("effect")]
        effect = primary["effect"]
        effect = re.sub(r"\s*[+＋]\s*", " +", effect)
        effect = re.sub(r"\s+", " ", effect).strip()
        table[stem] = {
            "name": pick_name(stem, primary["name"]),
            "effect": effect,
            "source": "%s:%s" % (primary["tower"], primary["key"]),
            "alternatives": alternatives,
        }

    io.open(OUT_PATH, "w", encoding="utf-8", newline="\n").write(
        json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print("写入 %s（%d 个图标）" % (OUT_PATH, len(table)))
    for stem, entry in table.items():
        print("  %-14s %-6s %s" % (stem, entry["name"], entry["effect"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
