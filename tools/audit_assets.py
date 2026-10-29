"""清点 assets/ 下哪些文件真的有人用，哪些是没人引用的死素材。

判定顺序：
1. 资源图标（assets/items/*.png）：名字被 map.json 的值、item_catalog.json 的键、
   item_effects.json 的键，或代码/测试/工具里当字面量出现过 → 有人用。
2. 素材库图（assets/library/**）：名字出现在 manifest.json（`file` 字段）或
   代码里当字面量 → 有人用。
3. 其它文件（icons/、items/ 的 json、assets 根下的 png/json/db）：按"文件名或
   去掉扩展名的名字在代码/配置里出现过"判。

只打印，不删。用法：
    python tools/audit_assets.py            # 报未引用
    python tools/audit_assets.py --delete   # 真删（打印删了哪些）
"""

import io
import json
import os
import re
import sys

ROOT = r"C:\Users\87790\dev\ChaitaAssistant"
ASSETS = os.path.join(ROOT, "assets")

# 这些不是"素材"，是配置/数据/生成物，永远不动
KEEP_NAMES = {
    "map.json", "item_catalog.json", "item_effects.json", "skill_effects.json",
    "skill_params.json", "monster_templates.json", "monster_templates.db",
    "manifest.json", "hero_icon.png",
}


def text_sources():
    """仓库里所有会被搜的文本（代码 / 测试 / 工具 / 配置 / 文档）。"""
    out = {}
    for folder in ("chaita", "tests", "tools", "docs"):
        for base, _dirs, files in os.walk(os.path.join(ROOT, folder)):
            for name in files:
                if name.endswith((".py", ".qml", ".md", ".json", ".yml", ".toml")):
                    path = os.path.join(base, name)
                    try:
                        with io.open(path, encoding="utf-8", errors="ignore") as h:
                            out[path] = h.read()
                    except OSError:
                        pass
    for name in ("README.md", "AGENTS.md", "pytest.ini", "environment.yml"):
        path = os.path.join(ROOT, name)
        if os.path.exists(path):
            with io.open(path, encoding="utf-8", errors="ignore") as h:
                out[path] = h.read()
    return out


def load(path):
    try:
        with io.open(path, encoding="utf-8-sig") as h:
            return json.load(h)
    except Exception:
        return {}


def main(argv):
    do_delete = "--delete" in argv
    texts = text_sources()
    blob = "\n".join(texts.values())

    referenced = set()
    # 1. 资源图标：配置里出现过的 stem
    map_json = load(os.path.join(ASSETS, "items", "map.json"))
    referenced |= {str(v) for v in map_json.values()}
    referenced |= set(load(os.path.join(ASSETS, "item_catalog.json")).keys())
    referenced |= set(load(os.path.join(ASSETS, "item_effects.json")).keys())
    # 2. 素材库：manifest 里登记的文件（`stem` / `path`），这一批是按目录摆出来的，
    #    代码里不会出现文件名，只能靠 manifest 认
    manifest = load(os.path.join(ASSETS, "library", "manifest.json"))
    for item in manifest.get("items") or []:
        for key in ("stem", "file", "name", "id"):
            if item.get(key):
                referenced.add(os.path.basename(str(item[key])))
        path = str(item.get("path") or "")
        if path:
            referenced.add(os.path.splitext(os.path.basename(path))[0])
    # 3. 显式不动的
    referenced |= KEEP_NAMES

    unused = []
    for base, _dirs, files in os.walk(ASSETS):
        for name in files:
            path = os.path.join(base, name)
            stem, ext = os.path.splitext(name)
            if name in KEEP_NAMES:
                continue
            if stem in referenced:
                continue
            # 代码里当字面量出现过（带引号的整名，避免 redKey 撞到 blueKey 这种前缀）
            token = re.escape(name)
            stem_token = re.escape(stem)
            if re.search(r"[\"'/]" + token + r"[\"']", blob):
                continue
            if re.search(r"[\"'/]" + stem_token + r"[\"']", blob):
                continue
            unused.append(os.path.relpath(path, ROOT))

    total = sum(len(f) for _b, _d, f in os.walk(ASSETS))
    print("assets 共 %d 个文件，未引用 %d 个" % (total, len(unused)))
    for rel in sorted(unused):
        print("  未引用:", rel)
    if do_delete:
        for rel in unused:
            os.remove(os.path.join(ROOT, rel))
        print("已删除 %d 个" % len(unused))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
