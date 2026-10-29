"""把用户给的血瓶/宝石精灵表切成单个图标，存到 assets/items/。

关键教训：**不能按 128÷行数 平均切**。血瓶那张表实际的行位置是 y=2..29 / 35..60 /
64..93，平均分（每格 42.7px）会把下一行的瓶口切进来，看上去就是"图标截到下面了"。
这里改成按"非透明像素的行/列投影"找出真实的行列边界再切。
"""

import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "items")

DOWNLOADS = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads")

# 精灵表里四列分别是这些颜色（对着图看的：红、紫、绿、黄）
COLORS = ["red", "purple", "green", "yellow"]

SHEETS = [
    ("血瓶1.png", "potion", 0, 4),   # 取第一行（圆瓶）
    ("宝石7.png", "gem", 0, 4),      # 取第一行
]


def load(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)


def bands(flags, min_gap=2):
    """把投影里连续的非零段找出来，返回 [(起, 止)]（止含）。"""
    out = []
    index = 0
    total = len(flags)
    while index < total:
        if flags[index] <= 0:
            index += 1
            continue
        start = index
        gap = 0
        while index < total:
            if flags[index] > 0:
                gap = 0
            else:
                gap += 1
                if gap >= min_gap:
                    break
            index += 1
        out.append((start, index - gap - 1 if gap else index - 1))
    return out


def alpha_or_bright(image):
    """透明的图用 alpha，不透明的用"非纯黑"当掩码。"""
    if image.ndim == 3 and image.shape[2] == 4:
        return (image[:, :, 3] > 16)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray > 8


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, prefix, want_row, _cols in SHEETS:
        path = os.path.join(DOWNLOADS, name)
        if not os.path.exists(path):
            print("跳过（找不到）", path)
            continue
        sheet = load(path)
        if sheet is None:
            print("读不出来", path)
            continue

        mask = alpha_or_bright(sheet)
        rows = bands(mask.sum(axis=1))
        cols = bands(mask.sum(axis=0))
        print("%s 行带 %s 列带 %s" % (name, rows, cols))
        if want_row >= len(rows) or len(cols) < len(COLORS):
            print("  行/列数量不符预期，跳过")
            continue

        top, bottom = rows[want_row]
        for color, (left, right) in zip(COLORS, cols):
            icon = sheet[top:bottom + 1, left:right + 1]
            target = os.path.join(OUT, "%s_%s.png" % (prefix, color))
            cv2.imwrite(target, icon)
            print("  写出", os.path.basename(target), icon.shape)


if __name__ == "__main__":
    main()
