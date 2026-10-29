"""把「AI 裁的图标」和「素材库里的同款」摆在一起，给 owner 一张对比图。

用途：老问题（图标要不要优先用现成切好的图）—— 那批图已经并进素材库
`assets/library/monster/`，这个脚本留着比对 AI 裁的图和切好的图。原话：第 10.4 / 19 节挂着"图标要不要优先用 `assets/monster_icons/` 里那 127 张
干净同款"。这件事我看不出该不该改（会改用户看到的图），所以出一张对比图让他一句话
决定 —— 而不是拿两张截图分别描述。

做法：
  1. 真读一次那张手册页（`docs/capture/_manual_repro.png`），拿到 AI 裁的图标；
  2. 按名字去 `assets/monster_templates.db` 查同款（含 aliases）；
  3. 左边 AI 裁的、右边库里那款，**都不缩放**（只按原始像素贴到网格里）；
  4. 拼成 `docs/capture/_icon_compare.png`，控制台打印行顺序。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\compare_icons.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2                                                # noqa: E402
import numpy as np                                        # noqa: E402

from chaita.game.agent.monster import read as monster_read  # noqa: E402
from chaita.ui.toolkit import library as ui_library        # noqa: E402

SAMPLE = os.path.join(ROOT, "docs", "capture", "_manual_repro.png")
OUT = os.path.join(ROOT, "docs", "capture", "_icon_compare.png")
DB = os.path.join(ROOT, "assets", "monster_templates.db")
CELL = 120


def library_icons() -> dict:
    """名字/别名 → 图标数组（只读本地库，不联网）。"""
    rows = ui_library._load_templates_from_db(DB) or []
    out = {}
    for row in rows:
        icon = str(row.get("icon") or "")
        if not icon.startswith("file:///"):
            continue
        path = icon[8:].replace("/", os.sep)
        if not os.path.exists(path):
            continue
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if image is None or image.size == 0:
            continue
        for name in [row.get("name")] + list(row.get("aliases") or []):
            text = str(name or "").strip()
            if text:
                out.setdefault(text, image)
    return out


def to_bgra(image) -> "np.ndarray":
    if image is None:
        return None
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    if image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    return image


def paste(canvas, tile, left, top) -> None:
    """把一块图按原始尺寸贴到画布上（超出格子就裁掉，绝不缩放）。"""
    if tile is None:
        return
    height, width = tile.shape[:2]
    height = min(height, canvas.shape[0] - top)
    width = min(width, canvas.shape[1] - left)
    if height <= 0 or width <= 0:
        return
    canvas[top:top + height, left:left + width] = tile[:height, :width]


def main() -> int:
    page = cv2.imread(SAMPLE)
    if page is None:
        print("读不到样图:", SAMPLE)
        return 1
    print("样图 %dx%d，正在读一次手册（约 20-60 秒）…" % (page.shape[1],
                                                      page.shape[0]))
    rows = monster_read(page)
    if not rows:
        print("这次没读出来，先不生成对比图")
        return 1
    lib = library_icons()
    print("素材库可查的图标名：%d 个" % len(lib))

    tiles = []
    for row in rows:
        name = str(row.get("name") or "")
        ai = to_bgra(row.get("icon"))
        same = lib.get(name)
        tiles.append((name, ai, same))
        print("  %-8s AI %s  素材库 %s" % (
            name,
            "有 %dx%d" % (ai.shape[1], ai.shape[0]) if ai is not None else "无",
            "有 %dx%d" % (same.shape[1], same.shape[0]) if same is not None
            else "没有同款"))

    canvas = np.zeros((CELL * len(tiles), CELL * 2, 4), np.uint8)
    canvas[:, :, 3] = 255
    canvas[:, :, :3] = 32                            # 深色底，和面板接近
    for index, (_name, ai, same) in enumerate(tiles):
        paste(canvas, ai, 0, index * CELL)
        paste(canvas, same, CELL, index * CELL)
        # 两列中间画一条分隔线，方便对照
        canvas[index * CELL:(index + 1) * CELL, CELL - 1:CELL] = (70, 70, 70, 255)

    ok = cv2.imwrite(OUT, canvas)
    print("已写", OUT, "成功" if ok else "失败")
    print("行顺序（从上到下）：%s" % "、".join(t[0] for t in tiles))
    print("左列 = AI 裁的（带底纹），右列 = 素材库同款（透明底）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
