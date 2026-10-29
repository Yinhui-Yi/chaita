"""从魔塔游戏的原始素材里提取状态栏图标。

素材来源：C:\\Users\\87790\\Downloads\\51\\51\\project\\materials
  icons.png  32x1376，43 个 32x32 图标竖排
  items.png  道具图标，32 像素一行

图标在素材里的序号来自游戏自己的配置，不是猜的：
  project/plugins.js       -> core.statusBar.icons（floor:0 lv:1 hp:3 atk:4 def:5
                              mdef:6 money:7 experience:8）
  project/icons.js         -> "items": {yellowKey:0, blueKey:1, redKey:2, greenKey:3}

    python tools/extract_icons.py
"""

import os

import cv2
import numpy as np

GAME = r"C:\Users\87790\Downloads\51\51\project\materials"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "icons")

# 状态栏图标在 icons.png 里的序号（来自 project/plugins.js 的 core.statusBar.icons）
ICONS_SHEET = {
    "lv": 1,
    "hp": 3,
    "atk": 4,
    "def": 5,
    "mdef": 6,
    "gold": 7,       # 配置里叫 money
    # 经验（配置里 'experience': 8）不提取：这一格画的是"破损的剑"，
    # 视觉上不是经验图标；界面改用「升级还需」表达，不再放经验图标。
}

# 钥匙在 items.png 里的行号（来自 project/icons.js 的 items 映射）
ITEMS_SHEET = {
    "key_yellow": 0,
    "key_blue": 1,
    "key_red": 2,
    "key_green": 3,
    # 面板上那三个工具：破（镐子）/ 炸（炸弹）/ 飞（对称飞行器）
    "tool_pick": 45,     # pickaxe
    "tool_bomb": 43,     # bomb
    "tool_fly": 13,      # centerFly，即对称飞行器
}


def imread_unicode(path):
    with open(path, "rb") as handle:
        data = np.frombuffer(handle.read(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)


def main():
    os.makedirs(OUT, exist_ok=True)

    icons_path = os.path.join(GAME, "icons.png")
    icons = imread_unicode(icons_path)
    if icons is None:
        raise SystemExit("读不到 %s" % icons_path)
    height, width = icons.shape[:2]
    tile = width  # 32x32 竖排
    print("icons.png %dx%d -> 每格 %d，共 %d 个" % (width, height, tile, height // tile))

    for name, index in ICONS_SHEET.items():
        top = index * tile
        crop = icons[top:top + tile, 0:tile]
        if crop.shape[0] != tile:
            print("  跳过 %s：序号 %d 超出范围" % (name, index))
            continue
        cv2.imwrite(os.path.join(OUT, name + ".png"), crop)
        print("   %-11s <- icons.png 第 %d 格" % (name, index))

    items_path = os.path.join(GAME, "items.png")
    items = imread_unicode(items_path)
    if items is None:
        print("读不到 items.png，钥匙图标跳过")
        return
    ih, iw = items.shape[:2]
    print("items.png %dx%d -> 每行 %d，共 %d 行" % (iw, ih, tile, ih // tile))

    for name, row in ITEMS_SHEET.items():
        top = row * tile
        crop = items[top:top + tile, 0:tile]
        if crop.shape[0] != tile:
            print("  跳过 %s：行号 %d 超出范围" % (name, row))
            continue
        cv2.imwrite(os.path.join(OUT, name + ".png"), crop)
        print("   %-11s <- items.png 第 %d 行" % (name, row))


if __name__ == "__main__":
    main()
