"""把模板库（`assets/monster_templates.db`）里失效的缩略图重新指回素材库的现有文件。

为什么会有失效的：模板库 18:10 建的，素材库 18:29 才按新命名规则重排编号
（`039_slime_man_...` → `047_slime_man_...`），库里 `icon` 还指着老文件名，
`test_editor.test_no_two_templates_look_the_same` 一读就 FileNotFoundError。

**不重建模板库**：重建会把用户逐张核对过的编号整体重排（docs/PICKER_TODO.md 红线）。

怎么找回来：库里每行都有 `(tower, key)`，素材库的 id 就是 `monster/<tower>_<key>`
（并掉的记在 `alias_ids` 里，`towers` 有多座塔时逐个试）——按 id 精确取路径，
不靠名字猜。id 全对不上时才退回"按贴图键后缀找"，且两个候选就报出来不猜。

    python tools/fix_template_icons.py            # 干跑，只报要改哪几行
    python tools/fix_template_icons.py --write    # 真写库
"""

import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "assets", "monster_templates.db")
MANIFEST = os.path.join(ROOT, "assets", "library", "manifest.json")
LIB = os.path.join(ROOT, "assets", "library", "monster")
STRIP_NUMBER = re.compile(r"^\d+_")


def load_index():
    """素材库 id（含被并掉的 id）→ 条目；顺带给出有哪些塔前缀。"""
    with open(MANIFEST, encoding="utf-8") as handle:
        items = (json.load(handle).get("items") or [])
    index = {}
    for entry in items:
        for key in [entry.get("id")] + list(entry.get("alias_ids") or []):
            if key:
                index[key] = entry
    towers = []
    for entry in items:
        name = entry.get("tower")
        if name and name not in towers:
            towers.append(name)
    return index, towers


def towers_of(row, known):
    """先试这一行自己的塔，再试别的塔（同一只怪在两座塔里只差 id 前缀）。"""
    names = [part.strip() for part in str(row.get("towers") or "").split(",")]
    names = [name for name in names if name]
    if row.get("tower"):
        names.insert(0, row["tower"])
    for name in known:
        if name not in names:
            names.append(name)
    return names


def asset_rel(path):
    """素材库给的是 `assets/library/...`，模板库里存的是相对 `assets/` 的 `library/...`
    （读库那侧拼 `file:///<assets>/` 前缀，多一层 assets 就打不开了）。"""
    text = str(path or "").replace("\\", "/")
    return text[len("assets/"):] if text.startswith("assets/") else text


def resolve(row, index, files, known):
    """这一行的图现在叫什么（相对 assets 的路径）；认不出来返回 ("", 原因)。"""
    key = str(row.get("key") or "")
    if key:
        for tower in towers_of(row, known):
            entry = index.get("monster/%s_%s" % (tower, key))
            if entry and entry.get("path"):
                return asset_rel(entry["path"]), ""
    # 退回按贴图键后缀找：老文件名的"编号_xxx.png"里 xxx 是稳定的
    old = os.path.basename(str(row.get("icon") or ""))
    stem = STRIP_NUMBER.sub("", old)
    hits = sorted(name for name in files
                  if STRIP_NUMBER.sub("", name) == stem)
    if len(hits) == 1:
        return "library/monster/" + hits[0], ""
    if len(hits) > 1:
        return "", "贴图键对上 %d 个文件，不猜：%s" % (len(hits), hits)
    return "", "素材库里没有这张图（贴图键 %r）" % (stem,)


def main(argv):
    write = "--write" in argv
    index, known = load_index()
    files = os.listdir(LIB)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(row) for row in con.execute(
        "select id, name, key, tower, towers, icon from enemy order by seq")]
    fixes = []
    dead = []
    for row in rows:
        rel = str(row["icon"] or "")
        if not rel or os.path.exists(os.path.join(ROOT, "assets", rel)):
            continue
        now, why = resolve(row, index, files, known)
        if now:
            fixes.append((row["id"], row["name"], rel, now))
        else:
            dead.append((row["id"], row["name"], rel, why))
    print("库里 %d 条，指着老文件的 %d 条，能修 %d 条，修不了 %d 条"
          % (len(rows), len(fixes) + len(dead), len(fixes), len(dead)))
    for _id, name, old, new in fixes:
        print("  %-3s %-8s %s -> %s"
              % (_id, name, os.path.basename(old), os.path.basename(new)))
    for _id, name, old, why in dead:
        print("  !! %-3s %-8s %s：%s" % (_id, name, os.path.basename(old), why))
    if not write:
        print("\n干跑，没写库。加 --write 才真改。")
        return 0 if not dead else 1
    with con:
        con.executemany("update enemy set icon = ? where id = ?",
                        [(new, _id) for _id, _name, _old, new in fixes])
    print("\n写好了：改了 %d 条。" % (len(fixes),))
    return 0 if not dead else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
