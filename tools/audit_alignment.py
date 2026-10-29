"""对齐体检：把一张渲染图里所有"有内容的横条"找出来，报每条的左右边界。

为什么用像素而不是 QML 的坐标：用户看到的是像素。QML 里 anchors 都"对"，
但字形的左右留白（bearing）、内边距、控件的 hit area 都会让**视觉**差几个像素，
这正是"看起来没对齐"的来源。

用法：
    python tools/audit_alignment.py docs/capture/_r3_chat_open.png

输出：每条内容的 y 范围 + 左边界 + 右边界（渲染像素）。基准：
    窗口 340 逻辑宽、150% 缩放 → 510 渲染像素；
    内容左边缘应为 15、右边缘应为 495（= card 10px 内边距）。
"""

import sys

import cv2
import numpy as np

# 渲染像素 → 逻辑像素
DPI = 1.5
# 内容基准（渲染像素）
GRID_LEFT = 10 * DPI
GRID_RIGHT = 510 - 10 * DPI


def bands(gray, alpha, threshold=95, min_gap=2):
    """按行扫描：连续有亮像素的行归为一条。"""
    mask = (gray > threshold) & (alpha > 200)
    rows = np.where(mask.any(axis=1))[0]
    if len(rows) == 0:
        return []
    out = []
    start = rows[0]
    prev = rows[0]
    for row in rows[1:]:
        if row - prev > min_gap:
            out.append((start, prev))
            start = row
        prev = row
    out.append((start, prev))
    return out


def span(gray, alpha, y0, y1, threshold=95):
    band = gray[y0:y1 + 1]
    mask = (alpha[y0:y1 + 1] > 200)
    cols = np.where(((band > threshold) & mask).any(axis=0))[0]
    return (int(cols[0]), int(cols[-1])) if len(cols) else (-1, -1)


def main(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print("读不到图：", path)
        return 1
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        alpha = np.full(img.shape[:2], 255, dtype=np.uint8)
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)

    print("== %s  (%dx%d) ==" % (path, img.shape[1], img.shape[0]))
    print("基准：内容左 %.0f / 右 %.0f（渲染像素）" % (GRID_LEFT, GRID_RIGHT))
    print("%-12s %-10s %6s %6s   %s" % ("y 范围", "行高", "左", "右", "偏差"))
    flagged = 0
    for y0, y1 in bands(gray, alpha):
        left, right = span(gray, alpha, y0, y1)
        if left < 0:
            continue
        # 整宽装饰线（顶栏闪光线、分隔线）本来就是通铺的，不算跑出网格
        full_bleed = left <= 2 and right >= img.shape[1] - 3
        notes = []
        if full_bleed:
            continue
        if left < GRID_LEFT - 3:
            notes.append("左溢出 %.0f" % (GRID_LEFT - left))
        if right > GRID_RIGHT + 3:
            notes.append("右溢出 %.0f" % (right - GRID_RIGHT))
        # 只报"明显离开网格"的行（超过 6px），否则太吵
        if notes:
            flagged += 1
        print("%-12s %-10s %6d %6d   %s"
              % ("%d-%d" % (y0, y1), "%dpx" % (y1 - y0 + 1), left, right,
                 "、".join(notes)))
    print("\n超出网格的行：%d 条（上面带字的那些）" % flagged)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
