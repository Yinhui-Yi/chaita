"""把两座塔里的**全部道具**做成资源：图标切出来 + 名字/效果整理成表。

用户："资源里资源种类不全怎么没有武器和防具还有钥匙"。

`assets/item_effects.json`（`tools/build_item_effects.py`）只整理了 血瓶/宝石 八件，
因为以前只认「颜色 + 种类」的图。塔里其实还有钥匙、剑、盾、书、特殊道具 ——
它们的图在 `project/materials/items.png`（32×32 一格，`project/icons.js` 的
`items` 段给 id → 行号），名字和说明在 `project/items.js`。

这里做两件事：
  1. 切图：`assets/items/<塔>_<id>.png`（原始像素，只去透明边，不放大）；
  2. 列表：`assets/item_catalog.json` —— `{图标名: {name, effect, cls, tower}}`，
     界面「＋ 加资源」和改名时按它查（`chaita/game/iteminfo.py` 会读）。

跑法：
    python tools/build_item_icons.py
"""

import io
import json
import os
import re
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

OUT_DIR = os.path.join(ROOT, "assets", "items")
CATALOG = os.path.join(ROOT, "assets", "item_catalog.json")

from build_item_effects import expand, objects, read, values_of   # noqa: E402

HOME = os.path.expanduser("~")
TOWERS = [
    ("rm", os.path.join(HOME, "Downloads", "xinxin",
                            "mota_pack_20260623_204744")),
    ("h5", os.path.join(HOME, "Downloads", "xinxin2new", "xinxin2")),
]
CELL = 32


def icon_rows(path):
    """icons.js 的 `items` 段：id → 第几格。"""
    text = read(path)
    start = text.find('"items"')
    if start < 0:
        return {}
    end = text.find("}", start)
    return {key: int(value) for key, value in
            re.findall(r'"([A-Za-z0-9_]+)"\s*:\s*(\d+)', text[start:end])}


def trim(image):
    if image is None:
        return None
    if image.ndim == 3 and image.shape[2] == 4:
        mask = image[:, :, 3] > 8
    elif image.ndim == 3:
        mask = (image[:, :, 0] + image[:, :, 1] + image[:, :, 2]) > 0
    else:
        return image
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None
    return image[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def clean_effect(body, values):
    """道具说明：模板里的 `${core.values.x}` 换成真数，剩下的去掉标记。"""
    tip = re.search(r'"itemEffectTip"\s*:\s*"([^"]*)"', body)
    text = re.search(r'"text"\s*:\s*"([^"]*)"', body)
    for match in (tip, text):
        if not match:
            continue
        raw = match.group(1)
        if "${" in raw:
            raw = expand(raw, values)
        raw = raw.replace("\\n", " ").replace("\\t", " ").replace('\\"', '"')
        raw = re.sub(r"\$\{[^}]*\}", "", raw)
        # 塔里的说明带脚本残渣（moneyPocket / 放在冒险袋中），去掉免得看不懂
        raw = raw.replace("moneyPocket", "").replace("放在冒险袋中", "")
        raw = re.sub(r"\s+", " ", raw).strip()
        raw = raw.lstrip("，,、;；:： ")
        if raw:
            return raw
    return ""


# 这些不是"资源"：技能面板按钮、攻略书、占位物品
SKIP_CLASSES = ("constants",)
SKIP_NAMES = ("新物品", "")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    catalog = {}
    written = 0
    skipped = 0
    for label, folder in TOWERS:
        proj = os.path.join(folder, "project")
        sheet_path = os.path.join(proj, "materials", "items.png")
        sheet = cv2.imdecode(np.fromfile(sheet_path, dtype=np.uint8),
                             cv2.IMREAD_UNCHANGED) if \
            os.path.exists(sheet_path) else None
        items = objects(read(os.path.join(proj, "items.js")))
        rows = icon_rows(os.path.join(proj, "icons.js"))
        values = values_of(read(os.path.join(proj, "data.js"))) \
            if os.path.exists(os.path.join(proj, "data.js")) else {}
        print("  %s：%d 件道具，%d 个有图" % (label, len(items), len(rows)))
        for item_id, body in items.items():
            name_match = re.search(r'"name"\s*:\s*"([^"]*)"', body)
            name = name_match.group(1) if name_match else ""
            kind = re.search(r'"cls"\s*:\s*"([^"]*)"', body)
            cls = kind.group(1) if kind else ""
            if (not name or name in SKIP_NAMES or cls in SKIP_CLASSES
                    or item_id not in rows):
                skipped += 1
                continue
            row = rows[item_id]
            stem = "%s_%s" % (label, item_id)
            path = os.path.join(OUT_DIR, stem + ".png")
            if sheet is not None and (row + 1) * CELL <= sheet.shape[0]:
                cell = sheet[row * CELL:(row + 1) * CELL, 0:CELL]
                cell = trim(cell)
                if cell is not None:
                    ok, buf = cv2.imencode(".png", cell)
                    if ok:
                        buf.tofile(path)
                        written += 1
            if not os.path.exists(path):
                skipped += 1
                continue
            catalog[stem] = {
                "name": name,
                "effect": clean_effect(body, values),
                "cls": cls,
                "tower": label,
                "item": item_id,
            }

    with io.open(CATALOG, "w", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=1,
                  sort_keys=True)
        handle.write("\n")
    print("资源图标 %d 张（跳过 %d），目录 %d 条：%s"
          % (written, skipped, len(catalog), CATALOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
