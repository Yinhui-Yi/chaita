"""素材库唯一的一条流水线：**切图 → 起名 → 排序 → manifest**。

用户："我下载里有两个新新魔塔的游戏，将那里面的怪物和名字加入素材库，
把之前的素材都删掉。"

图只存一处：`assets/library/monster/`（用户："monster_icons为什么不删？"），
文件名按 `library.file_stem()`：种族 + 英文名、全 ASCII（规则在
`chaita/library_names.py`）。`id` 仍是 `monster/<塔>_<贴图键>`（存盘/`icon_id`
的稳定键）。顺带把 `assets/monster_templates.json` 的 `icon` 指到这些文件上 ——
以前这一步在 `tools/build_monster_icons.py` 里，两个脚本各自算一遍文件名，
迟早对不上，所以合成一个（那个脚本已经删了）。

为什么图要"切"：enemys.js 里**没有图片字段**（只有个别 boss 有 `bigImage`），
怪物的图在 `project/materials/enemys.png`（32×32 一格、一行一只、两帧）和
`enemy48.png`（32×48 一格、四帧）里，位置由 `project/icons.js` 的
`enemys` / `enemy48` 段给出（id → 行号）。这里只按格子裁 + 去透明边，**不放大**。

`assets/library/` 下**别的东西一律删掉**（旧分类目录、对不上的旧图）。

跑法：
    python tools/build_library.py [塔1目录] [塔2目录]
"""

import hashlib
import io
import json
import os
import re
import shutil
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chaita import library as asset_library            # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
LIB = os.path.join(ASSETS, "library")
MONSTER_DIR = os.path.join(LIB, "monster")
MANIFEST = os.path.join(LIB, "manifest.json")
TEMPLATES = os.path.join(ASSETS, "monster_templates.json")

# 太小的格子不算图（空的 32×48 格切出来是 0 像素，别塞进素材库）
MIN_SIDE = 2

HOME = os.path.expanduser("~")
DEFAULT_TOWERS = [
    os.path.join(HOME, "Downloads", "xinxin", "mota_pack_20260623_204744"),
    os.path.join(HOME, "Downloads", "xinxin2new", "xinxin2"),
]
TOWER_LABELS = ["xinxin", "xinxin2"]


def read_png(path):
    if not os.path.exists(path):
        return None
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)


def parse_enemys(path):
    """enemys.js 是 JSON 里的一坨对象字面量：id → {name, hp, atk, def, bigImage}。

    不能拿 `"id": {…}` 的正则硬切：条目里有嵌套的 `{}`（技能参数之类），
    一刀切下去会把**后面那只怪的名字**算到前一只头上（实测 `evilBat` 被叫成
    「丧尸士兵」，于是两张不同的图被当成重复并掉）。这里按花括号配对取整段。
    """
    try:
        text = io.open(path, encoding="utf-8").read()
    except OSError:
        return {}
    out = {}
    for match in re.finditer(r'"(\w+)"\s*:\s*\{', text):
        body = brace_body(text, match.end() - 1)
        if '"name"' not in body:
            continue

        def field(key):
            found = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, body)
            if found:
                return found.group(1)
            found = re.search(r'"%s"\s*:\s*(-?\d+)' % key, body)
            return int(found.group(1)) if found else 0

        out[match.group(1)] = {"name": str(field("name") or ""),
                               "hp": int(field("hp") or 0),
                               "atk": int(field("atk") or 0),
                               "def": int(field("def") or 0),
                               "bigImage": str(field("bigImage") or "")}
    return out


def brace_body(text, start):
    """`text[start] == '{'` → 配到的那一段（含花括号；跳过字符串里的括号）。"""
    depth = 0
    index = start
    quoted = False
    while index < len(text):
        char = text[index]
        if quoted:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
        index += 1
    return text[start:]


def parse_icon_section(path, section):
    """icons.js 里某一段：id → 行号。"""
    try:
        text = io.open(path, encoding="utf-8").read()
    except OSError:
        return {}
    start = text.find('"%s": {' % section)
    if start < 0:
        return {}
    end = text.index("}", start)
    return {key: int(value) for key, value in
            re.findall(r'"(\w+)":\s*(\d+)', text[start:end])}


def load_tower(label, path):
    proj = os.path.join(path, "project")
    return {
        "label": label,
        "dir": path,
        "enemys": parse_enemys(os.path.join(proj, "enemys.js")),
        "locs": parse_icon_section(os.path.join(proj, "icons.js"), "enemys"),
        "locs48": parse_icon_section(os.path.join(proj, "icons.js"), "enemy48"),
        "sheet": read_png(os.path.join(proj, "materials", "enemys.png")),
        "sheet48": read_png(os.path.join(proj, "materials", "enemy48.png")),
        "images": os.path.join(proj, "images"),
    }


def trim(image):
    """去掉四周透明边（只裁，不缩放、不放大）。"""
    if image is None:
        return None
    if image.ndim == 3 and image.shape[2] == 4:
        mask = image[:, :, 3] > 8
    elif image.ndim == 3:
        mask = (image[:, :, 0] + image[:, :, 1] + image[:, :, 2]) > 0
    else:
        return image
    ys, xs = np.where(mask)
    if len(ys) == 0 or len(xs) == 0:
        return None
    return image[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def sprite_for(tower_info, eid):
    """按 id 取原始像素：32 格 → 32 格；48 格 → 32×48；boss → images/bigImage。"""
    if eid in tower_info["locs"] and tower_info["sheet"] is not None:
        row = tower_info["locs"][eid]
        return tower_info["sheet"][row * 32:(row + 1) * 32, 0:32], "32"
    if eid in tower_info["locs48"] and tower_info["sheet48"] is not None:
        row = tower_info["locs48"][eid]
        return tower_info["sheet48"][row * 48:(row + 1) * 48, 0:32], "48"
    big = tower_info["enemys"].get(eid, {}).get("bigImage") or ""
    if big:
        image = read_png(os.path.join(tower_info["images"], big))
        if image is not None:
            return image, "big"
    return None, ""


def opaque_ratio(image) -> float:
    """不透明像素占比：1.0 = 整块 32×32 都是实心的（图里带着底纹/背景），越小越干净。"""
    if image is None or image.ndim != 3 or image.shape[2] < 4:
        return 1.0
    alpha = image[:, :, 3]
    return float(np.mean(alpha > 200))


def cleanliness(image) -> tuple:
    """同一只怪有好几张时，按这个挑**最干净**的那张（小的优先）。

    用户："为什么同素材你删了没背景的，保留了有背景的？" —— 以前是"先出现的留下"，
    于是 `xinxin` 那种整块不透明的格子（底纹被烤进像素）会盖掉另一座塔干净的那张。
    """
    if image is None:
        return (9.0, 0)
    return (round(opaque_ratio(image), 3), -int(image.shape[0] * image.shape[1]))


def shape_diff(a, b) -> float:
    """两张图的**轮廓**差多少（只看 alpha 遮罩，不管颜色）。"""
    if a is None or b is None:
        return 1.0
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]),
                       interpolation=cv2.INTER_NEAREST)
    mask_a = a[:, :, 3] > 128
    mask_b = b[:, :, 3] > 128
    return float(np.mean(mask_a != mask_b))


def colour_diff(a, b) -> float:
    """两图**肉眼能看出来**不一样的像素占比（0.0–1.0）。

    以前用 `a != b`：编码/抗锯齿带来的 ±1 噪声也算“不同”，同一只红史莱姆
    两座塔的版本会被算成 31.5% 不同，于是该并的没并（用户："1，2重复了看不出来吗"）。
    现在按通道差 >24 才算不同 —— 实测同一张画 ≤0.2%，换色的（红/金 16.9 平均色差）
    仍在 90% 以上。
    """
    if a is None or b is None:
        return 1.0
    if a.shape != b.shape:
        # 只差 1–2 像素（比如 21×18 和 21×17）还是同一张画：缩到同一尺寸再比，
        # **只为比较，不落盘**（AGENTS 里那条"禁止预处理"说的是喂给模型/显示的路径）
        b = cv2.resize(b, (a.shape[1], a.shape[0]),
                       interpolation=cv2.INTER_NEAREST)
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return float(np.mean(delta.max(axis=2) > 24))


# 同一张画的差异上限：容差后的比例，同一张画实测 ≤0.2%，换色版 90% 以上，取 2%。
SAME_ART_DIFF = 0.02


def colour_of(image) -> str:
    """这张图主色是什么（只看肉眼看见的部分），用来排魔塔的颜色档位。

    用户："魔塔最基本的强弱排序蓝绿黄红黑" —— 档位得按**图上的颜色**排，
    不能按名字里有没有"蓝/绿/黄/红/黑"（名字经常不带颜色）。
    """
    if image is None or image.ndim != 3 or image.shape[2] < 4:
        return ""
    alpha = image[:, :, 3] > 128
    if not alpha.any():
        return ""
    pixels = image[:, :, :3][alpha].astype(np.float32) / 255.0
    b, g, r = pixels[:, 0].mean(), pixels[:, 1].mean(), pixels[:, 2].mean()
    value = max(r, g, b)
    if value < 0.28:
        return "black"
    low = min(r, g, b)
    if value - low < 0.10:
        return "grey"
    if value > 0.80 and low > 0.70:
        return "white"
    if r >= g and r >= b:
        return "red" if g < r * 0.75 else "yellow"
    if g >= r and g >= b:
        return "green" if r < g * 0.85 else "yellow"
    return "blue" if g < b * 0.85 else "purple"


def fingerprint(image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()[:16]


def cleanup(keep: set) -> int:
    """把素材库里"不是这次切出来的"东西删掉（用户："把之前的素材都删掉"）。"""
    removed = 0
    for name in os.listdir(LIB):
        path = os.path.join(LIB, name)
        if os.path.isdir(path) and name != "monster":
            shutil.rmtree(path)
            removed += 1
    for name in os.listdir(MONSTER_DIR):
        if name not in keep:
            os.remove(os.path.join(MONSTER_DIR, name))
            removed += 1
    return removed


def sync_templates(entries) -> int:
    """`monster_templates.json` 的 `icon` 指到素材库里的那张图。

    `icon_from` 记的是 `塔:贴图键:尺寸`，按它查 manifest —— 查不到就留空，
    免得指着一个不存在的文件。路径**相对 `assets/`**
    （`library/monster/001_...png`）：界面那边是 `file:///<assets>/` + 这个值拼 URL。
    """
    if not os.path.exists(TEMPLATES):
        return 0
    templates = json.load(io.open(TEMPLATES, encoding="utf-8"))
    paths = {(item["tower"], item["eid"]): _rel(item["path"])
             for item in entries}
    by_eid = {}
    for item in entries:
        by_eid.setdefault(item["eid"], _rel(item["path"]))
    changed = 0
    for item in templates:
        parts = str(item.get("icon_from") or "").split(":")
        path = ""
        if len(parts) >= 2:
            path = (paths.get((parts[0], parts[1]))
                    or by_eid.get(parts[1]) or "")
        if path != str(item.get("icon") or ""):
            item["icon"] = path
            changed += 1
    with io.open(TEMPLATES, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(templates, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return changed


def _rel(path: str) -> str:
    """`assets/library/monster/x.png` → `library/monster/x.png`（相对 assets）。"""
    text = str(path or "").replace("\\", "/")
    return text[len("assets/"):] if text.startswith("assets/") else text


def main() -> int:
    towers = DEFAULT_TOWERS
    if len(sys.argv) > 2:
        towers = sys.argv[1:3]
    parsed = []
    for label, path in zip(TOWER_LABELS, towers):
        if os.path.isdir(path):
            parsed.append(load_tower(label, path))
        else:
            print("跳过（不存在）：%s" % path)
    if not parsed:
        print("两座塔目录都没有，退出")
        return 1

    os.makedirs(MONSTER_DIR, exist_ok=True)
    # 第一趟：切图 + 按像素去重（两座塔同一张图只留一份），先不落盘 ——
    # 文件名带显示序号（用户："给素材名字里加ID确保弱的在前面"），
    # 序号要排完序才知道，所以落盘放到第二趟。
    entries = []
    sprites = {}
    seen = {}
    candidates = []
    missing = []
    hidden = []
    skipped = 0
    for info in parsed:
        label = info["label"]
        for eid in sorted(info["enemys"]):
            stats = info["enemys"][eid]
            name = str(stats.get("name") or "").strip()
            if not name:
                continue
            # 看图之后改过名的（塔里的名字跟图对不上，见 library_names.ART_NAMES）
            name = asset_library.library_names.ART_NAMES.get((label, eid), name)
            # 占位/废弃的**根本不收**（用户："asura不是让你删了吗"）：
            # 不是"摆的时候藏起来"，连文件都不该有
            if name in asset_library.HIDDEN_NAMES or any(
                    word in name for word in asset_library.HIDDEN_WORDS):
                hidden.append(name)
                continue
            sprite = trim(sprite_for(info, eid)[0])
            if sprite is None or min(sprite.shape[:2]) < MIN_SIDE:
                missing.append("%s:%s" % (label, eid))
                continue
            digest = fingerprint(sprite)
            if digest in seen:
                # 像素完全一样：同一张图，只留一份；被并掉的 id 记成别名，
                # 存档里的 icon_id 照样能查到这张图
                kept = seen[digest]
                kept.setdefault("alias_ids", []).append(
                    "monster/%s_%s" % (label, eid))
                if name not in kept["names"]:
                    kept["names"].append(name)
                skipped += 1
                continue
            kind = asset_library.kind_of(eid, name) or ""
            item = {
                "id": "monster/%s_%s" % (label, eid),
                "category": "monster",
                "name": name,
                "names": [name],
                "tower": label,
                "eid": eid,
                "hp": int(stats.get("hp") or 0),
                "atk": int(stats.get("atk") or 0),
                "def": int(stats.get("def") or 0),
                "sha256": digest,
                "colour": colour_of(sprite),
            }
            # 编号用**精灵表里的行号**（icons.js 给的那一格）：同一座塔里从上到下，
            # 用户："你看原素材排得多好" —— 文件按它排，就是游戏里那张精灵表的顺序
            row = info["locs"].get(eid)
            if row is None:
                row = info["locs48"].get(eid, 10 ** 5)
            item["seq"] = (0 if label == "xinxin" else 1, row, eid)
            seen[digest] = item
            # 先都当候选：后面合并同名、再挑最干净的那张
            candidates.append((name, item, sprite))

    # 合并：**只并"同名"的**（两座塔各存一份同一只怪）。
    # 曾经还按"轮廓一样"合并，结果把红色史莱姆并进黄金史莱姆、骑士并进铁骑士、
    # 骷髅兵并进灵骷髅 —— 换色的东西不是同一只怪（用户："错的东西太多了"）。
    # 用列表而不是 dict：以前拿名字当键，两只**同名不同画**的怪会互相顶掉
    # （xinxin 的 E336「毒龙」就是这么整只消失的）
    groups = []
    merged_away = set()
    for name, item, sprite in candidates:
        joined = None
        for group in groups:
            for member, other_sprite in group:
                # 只并**同一张画**（像素差 ≤2%）。同名不并 —— 两座塔里同名的两只
                # 可能根本不是一个东西（"骑士"在一座塔是黄甲骑士、另一座是红甲），
                # 用户："006是史莱姆吗？" 就是我按名字硬并出来的错。
                # 同一张画（容差内）→ 并；同名且**轮廓一样**（换色/重绘）→ 也并
                # 用户："看到重复的就删"。同名但轮廓差得远的（毒龙：一团绿 vs 一条龙）留着。
                same_art = colour_diff(sprite, other_sprite) <= SAME_ART_DIFF
                same_monster = (member["name"] == name
                                and shape_diff(sprite, other_sprite) <= 0.15)
                if same_art or same_monster:
                    joined = group
                    break
            if joined is not None:
                break
        if joined is None:
            groups.append([(item, sprite)])
        else:
            joined.append((item, sprite))

    # 看图定的"同一张画、两个名字"（`library_names.ART_MERGES`）：并到留下的那只头上
    for keep, drops in asset_library.library_names.ART_MERGES.items():
        kept = next((one for one in candidates
                     if (one[1]["tower"], one[1]["eid"]) == keep), None)
        if kept is None:
            continue
        for drop in drops:
            other = next((one for one in candidates
                          if (one[1]["tower"], one[1]["eid"]) == drop), None)
            if other is None:
                continue
            kept[1].setdefault("alias_ids", []).append(other[1]["id"])
            for alias in other[1].get("names") or []:
                if alias not in kept[1]["names"]:
                    kept[1]["names"].append(alias)
            merged_away.add((other[1]["tower"], other[1]["eid"]))
            skipped += 1
    if merged_away:
        groups = [[one for one in group
                   if (one[0]["tower"], one[0]["eid"]) not in merged_away]
                  for group in groups]
        groups = [group for group in groups if group]

    for members in groups:
        # 最干净的当正主（不带底纹、没有实心背景），其余记成别名 id
        members = sorted(members, key=lambda one: cleanliness(one[1]))
        item, sprite = members[0]
        for other, _s in members[1:]:
            item.setdefault("alias_ids", []).append(other["id"])
            for alias in other.get("names") or []:
                if alias not in item["names"]:
                    item["names"].append(alias)
            skipped += 1
        sprites[(item["tower"], item["eid"])] = sprite
        entries.append(item)

    # 编号 = **精灵表原来的行序**（先 xinxin 再 xinxin2，各自按 icons.js 的 id 顺序）：
    # 用户："你看原素材排得多好" —— 文件按这个编号排，看起来就是游戏里的顺序。
    # 合并时留下的那只按**最先出现**的那格算位置。
    entries.sort(key=lambda one: one.get("seq") or (9, 0, ""))
    for index, item in enumerate(entries):
        item["sheet_index"] = index
        item.pop("seq", None)

    # 显示顺序另算：同类相连、弱的在前、类按各自最弱的那只排
    entries = asset_library.arrange(entries)

    # 第二趟：按排好的顺序落盘（文件名 = 序号_种族_名字）
    kept_files = set()
    for item in entries:
        sprite = sprites.get((item["tower"], item["eid"]))
        if sprite is None:
            continue
        stem = asset_library.file_stem(item)
        ok, buf = cv2.imencode(".png", sprite)
        if not ok:
            continue
        buf.tofile(os.path.join(MONSTER_DIR, stem + ".png"))
        kept_files.add(stem + ".png")
        item["path"] = "assets/library/monster/%s.png" % stem
        item["stem"] = stem
        item["width"] = int(sprite.shape[1])
        item["height"] = int(sprite.shape[0])

    removed = cleanup(kept_files)
    with io.open(MANIFEST, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"count": len(entries), "items": entries}, handle,
                  ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")
    synced = sync_templates(entries)

    by_tower = {}
    by_kind = {}
    for item in entries:
        by_tower[item["tower"]] = by_tower.get(item["tower"], 0) + 1
        key = item.get("kind") or asset_library.UNKNOWN_KIND
        by_kind[key] = by_kind.get(key, 0) + 1
    print("素材库：%d 张怪物图（%s），删掉旧素材 %d 项，模板图标对上 %d 条"
          % (len(entries),
             "、".join("%s %d" % (key, value)
                      for key, value in sorted(by_tower.items())),
             removed, synced))
    print("  分类（按显示顺序）：%s"
          % "、".join("%s %d" % (key, by_kind[key]) for key in
                     [name for name in asset_library.KIND_NAMES
                      if name in by_kind]
                     + ([asset_library.UNKNOWN_KIND]
                        if asset_library.UNKNOWN_KIND in by_kind else [])))
    if skipped:
        print("  跳过（两座塔同一张图）：%d" % skipped)
    if missing:
        print("  切不出图（精灵表里没这一格）：%s" % "、".join(missing[:10]))
    print("manifest:", MANIFEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
