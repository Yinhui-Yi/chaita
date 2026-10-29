"""把素材库的图片文件按「种族 + 英文名」重命名（`xinxin2_E380.png` → `guard_war_god_goba.png`）。

用户："素材为什么不重新命名？" —— 文件名照抄塔里的贴图键，在图库/资源管理器里
根本看不出是哪只怪。名字口径见 `chaita/library_names.py`：**种族 + 名字、全 ASCII、
不许中文也不许拼音**。这里按 `chaita.library.file_stem()` 重命名，manifest 里的
`path` / `source` 一起改；**`id` 不动**（`monster/<塔>_<贴图键>` 是稳定键，
存盘的 `icon_id` 靠它），所以已经记下来的怪靠 `icon_id` 照样能找到图。

撞名不许悄悄加后缀：那说明 `library_names.NAME_ASCII` 需要改，直接报错退出。

用法：
    python tools/rename_library_files.py            # 真改
    python tools/rename_library_files.py --dry-run  # 只打印要改的名字
"""

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chaita import library                            # noqa: E402

MANIFEST = os.path.join(ROOT, "assets", "library", "manifest.json")
FOLDER = os.path.join(ROOT, "assets", "library", "monster")


def main(argv):
    dry = "--dry-run" in argv[1:]
    data = json.load(io.open(MANIFEST, encoding="utf-8"))
    items = data.get("items") or []
    # 先全部改成临时名，避免"改成的新名字正好是另一张的老名字"互相覆盖
    plan = []
    used = {}
    for item in items:
        stem = library.file_stem(item)
        if stem in used:
            print("撞名：%s（%s 和 %s）—— 改 chaita/library_names.py 的 NAME_ASCII"
                  % (stem, used[stem], item.get("id")))
            return 1
        used[stem] = item.get("id")
        old = os.path.join(ROOT, str(item.get("path") or ""))
        new = os.path.join(FOLDER, stem + ".png")
        plan.append((item, old, new))

    changed = [(item, old, new) for item, old, new in plan if old != new]
    if dry:
        for _item, old, new in changed:
            print("%-28s -> %s" % (os.path.basename(old), os.path.basename(new)))
        print("要改 %d 个文件（%d 条素材）"
              % (len(changed), len(items)))
        return 0

    # 两段式：先改成 .tmp，再改成最终名
    stage = []
    for index, (item, old, new) in enumerate(plan):
        if not os.path.exists(old):
            print("缺文件，跳过：%s" % old)
            continue
        temp = os.path.join(FOLDER, "__rename_%03d.tmp" % index)
        os.replace(old, temp)
        stage.append((item, temp, new))
    for item, temp, new in stage:
        os.replace(temp, new)
        item["path"] = os.path.relpath(new, ROOT).replace("\\", "/")
        item.pop("source", None)        # 图只存一处，文件名就是来源，别再记副本路径

    with io.open(MANIFEST, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    library._CACHE.clear()          # 让下一次 load 重新读
    print("改完 %d 个文件" % len(stage))
    print("例子：%s" % ", ".join(os.path.basename(new)
                                for _item, _temp, new in stage[:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
