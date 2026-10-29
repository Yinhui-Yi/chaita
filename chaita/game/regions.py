"""从游戏窗口截图中切出两块区域：状态面板 与 地图。

这是需求里唯一需要的几何处理 —— 不做网格定位、不做逐格识别。

切法不写死坐标，而是按画面结构自动推断，这样换窗口大小、换分辨率都不用重配：

  画布 = 画面里的非黑区域（两种魔塔都是黑底，画面之外是黑边/浏览器背景）
  纵向 = 画布内"连续有色"的行范围，去掉底部黑边
  分界 = 从左往右扫，找"状态面板"与"地图区"之间的断口

断口怎么找：状态面板是稀疏文字/图标，列能量低；地图区是密铺图块，列能量高。
所以取列能量的分位阈值，找第一个"持续高能量"的起点。
"""

from dataclasses import dataclass

import cv2
import numpy as np

# 判定"非黑"的灰度阈值
DARK = 25

# 地图区分界扫描：需要连续多少列高能量才算进入地图
RUN_COLS = 40


@dataclass
class Regions:
    """一块画面里的两块区域，坐标是相对截图的像素值。"""

    panel: tuple   # (x, y, w, h) 状态面板
    map: tuple     # (x, y, w, h) 地图区
    canvas: tuple  # (x, y, w, h) 整块游戏画布

    def __str__(self) -> str:
        return "面板=%s 地图=%s 画布=%s" % (self.panel, self.map, self.canvas)


def find_canvas(image: np.ndarray, top_skip: int = 0) -> tuple:
    """找非黑内容区的包围盒。

    top_skip 用于跳过窗口标题栏（抓图里会带上）。
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if top_skip:
        gray = gray[top_skip:, :]
    mask = gray > DARK
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return (0, 0, image.shape[1], image.shape[0])
    y = int(rows[0]) + top_skip
    y2 = int(rows[-1]) + top_skip
    x = int(cols[0])
    x2 = int(cols[-1])
    return (x, y, x2 - x + 1, y2 - y + 1)


def find_panel_split(canvas_gray: np.ndarray, default_ratio: float = 0.25) -> int:
    """在画布内找状态面板与地图区的分界列（相对画布左边）。

    地图区图块密铺，列方向能量高且连续；状态面板是黑底稀疏文字，能量低。
    """
    col_energy = canvas_gray.mean(axis=0)
    if col_energy.max() <= 0:
        return int(canvas_gray.shape[1] * default_ratio)

    threshold = max(DARK, col_energy.max() * 0.35)
    run = 0
    for x in range(len(col_energy)):
        if col_energy[x] > threshold:
            run += 1
            if run >= RUN_COLS:
                return x - run + 1
        else:
            run = 0
    return int(canvas_gray.shape[1] * default_ratio)


def split(image: np.ndarray, top_skip: int = 0,
          panel_width_ratio: float = None) -> Regions:
    """把一张游戏截图切成状态面板与地图两块。

    panel_width_ratio 给定时不自动找分界，直接按比例切 —— 有些塔的面板与
    地图颜色接近，自动分界会失手，这时用塔描述里的固定比例更稳。
    """
    canvas = find_canvas(image, top_skip=top_skip)
    cx, cy, cw, ch = canvas
    canvas_img = image[cy:cy + ch, cx:cx + cw]
    gray = cv2.cvtColor(canvas_img, cv2.COLOR_BGR2GRAY)

    if panel_width_ratio is not None:
        split_x = int(round(cw * panel_width_ratio))
    else:
        split_x = find_panel_split(gray)
    split_x = max(1, min(cw - 1, split_x))

    panel = (cx, cy, split_x, ch)
    map_rect = (cx + split_x, cy, cw - split_x, ch)
    return Regions(panel=panel, map=map_rect, canvas=canvas)


def crop(image: np.ndarray, rect: tuple) -> np.ndarray:
    x, y, w, h = rect
    return image[y:y + h, x:x + w]


def _bright_runs(values: np.ndarray, threshold: float, min_len: int):
    """找连续高于阈值的区间。返回 [(起, 止, 长度), ...]。"""
    result = []
    index = 0
    length = len(values)
    while index < length:
        if values[index] > threshold:
            end = index
            while end < length and values[end] > threshold:
                end += 1
            if end - index >= min_len:
                result.append((index, end - 1, end - index))
            index = end
        else:
            index += 1
    return result


def _merge_runs(runs, max_gap: int):
    """把间隔很小的区间合并。

    实测面板和地图之间有一条暗分隔线（几像素宽），会被切成两个独立区间。
    不合并的话"最长区间"只会选中地图，面板就被排除在画布之外了。
    """
    if not runs:
        return runs
    merged = [list(runs[0])]
    for start, end, length in runs[1:]:
        prev = merged[-1]
        if start - prev[1] <= max_gap:
            prev[1] = end
            prev[2] = prev[1] - prev[0] + 1
        else:
            merged.append([start, end, length])
    return [tuple(item) for item in merged]


def detect_h5_canvas(image: np.ndarray, threshold: float = 30.0,
                     panel_ratio: float = 0.24):
    """自动找出 h5 魔塔的画布，并按「左侧面板 + 右侧地图」切开。

    实测两座 h5 塔（喵塔、cxd_imprisoned）界面完全不同，但结构一致：
      页面背景近黑（灰度 ~7~9）
      画布内容亮（> 40）：左侧面板较暗（~70~85），右侧地图较亮（~100~150），
      两者之间只有几像素的暗分隔线
      地图是正方形
      面板占画布宽 23.7%~24.1%
    所以不必为每座塔写死坐标。窗口缩放、换一座同结构的塔，都不用重新标定。

    返回 (panel_rect, map_rect, canvas_rect)，坐标是整图像素。
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape

    col_runs = _bright_runs(gray.mean(axis=0), threshold, max(40, width // 40))
    col_runs = _merge_runs(col_runs, max_gap=max(6, width // 200))
    if not col_runs:
        return None, None, None
    left, right, _ = max(col_runs, key=lambda run: run[2])

    row_profile = gray[:, left:right + 1].mean(axis=1)
    row_runs = _bright_runs(row_profile, threshold, max(30, height // 40))
    row_runs = _merge_runs(row_runs, max_gap=max(6, height // 200))
    if not row_runs:
        return None, None, None
    top, bottom, _ = max(row_runs, key=lambda run: run[2])

    canvas = (left, top, right - left + 1, bottom - top + 1)
    # 地图一定是正方形、且贴在画布右边：用画布高度当边长，从右边量。
    # 以前按 panel_ratio(24%) 从左边硬切 —— 遇到"状态面板底色是纯黑"的塔
    # （亮区直接就是地图），会把地图最左边几列裁掉（用户："地图不全"）。
    map_side = min(canvas[2], canvas[3])
    map_rect = (canvas[0] + canvas[2] - map_side, top, map_side, map_side)
    panel_w = max(0, canvas[2] - map_side)
    panel = (left, top, panel_w, canvas[3])
    return panel, map_rect, canvas


def trim_black(image: np.ndarray, threshold: int = 22, min_keep: float = 0.5):
    """裁掉四周整条的黑边。

    区域坐标是按参考尺寸量的，窗口尺寸一变就可能多带进一点画布外的黑底
    （实测 h5 地图下方就多了一条）。与其为每个尺寸手调坐标，不如把边缘上
    "整行/整列都是黑"的部分去掉。每边最多裁掉 min_keep 之外的部分，避免
    把合理的黑底内容也裁没了。
    """
    if image is None or image.size == 0:
        return image
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark_row = gray.max(axis=1) <= threshold
    dark_col = gray.max(axis=0) <= threshold

    height, width = gray.shape
    max_rows = int(height * (1 - min_keep))
    max_cols = int(width * (1 - min_keep))

    top = 0
    while top < max_rows and dark_row[top]:
        top += 1
    bottom = height
    while height - bottom < max_rows and dark_row[bottom - 1]:
        bottom -= 1
    left = 0
    while left < max_cols and dark_col[left]:
        left += 1
    right = width
    while width - right < max_cols and dark_col[right - 1]:
        right -= 1

    if right - left < 8 or bottom - top < 8:
        return image
    return image[top:bottom, left:right]



