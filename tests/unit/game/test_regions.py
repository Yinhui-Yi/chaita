"""区域切分单元测试（`chaita/game/regions.py`）。

真值来自规则：非黑包围盒、列能量分界、正方形地图贴右、trim_black 裁黑边。
cv2/numpy 是真依赖，用合成小图手推期望。
"""

import numpy as np

import chaita.game.regions as R


def test_bright_runs():
    vals = np.array([0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0])
    assert R._bright_runs(vals, 0.5, 2) == [(2, 4, 3)]


def test_merge_runs():
    runs = [(0, 3, 4), (5, 8, 4), (20, 22, 3)]
    assert R._merge_runs(runs, max_gap=2) == [(0, 8, 9), (20, 22, 3)]


def test_merge_runs_empty():
    assert R._merge_runs([], 2) == []


def test_find_canvas_bounding_box():
    img = np.zeros((10, 10, 3), np.uint8)
    img[2:5, 3:8] = 255
    assert R.find_canvas(img) == (3, 2, 5, 3)


def test_find_canvas_all_black():
    img = np.zeros((5, 5, 3), np.uint8)
    assert R.find_canvas(img) == (0, 0, 5, 5)


def test_find_panel_split_no_energy_uses_default_ratio():
    gray = np.zeros((5, 10), np.uint8)
    assert R.find_panel_split(gray, default_ratio=0.25) == 2


def test_find_panel_split_finds_run_start():
    gray = np.zeros((5, 60), np.float32)
    gray[:, 20:] = 200.0
    assert R.find_panel_split(gray) == 20


def test_crop():
    img = np.arange(100).reshape(10, 10)
    out = R.crop(img, (2, 3, 4, 5))
    assert out.shape == (5, 4)
    assert out[0, 0] == img[3, 2]


def test_split_fixed_ratio():
    img = np.zeros((20, 40, 3), np.uint8)
    img[5:15, 0:40] = 150
    regions = R.split(img, top_skip=0, panel_width_ratio=0.25)
    assert regions.panel == (0, 5, 10, 10)
    assert regions.map == (10, 5, 30, 10)


def test_trim_black_cuts_borders():
    img = np.zeros((20, 20, 3), np.uint8)
    img[5:15, 5:15] = 200
    out = R.trim_black(img, threshold=22, min_keep=0.5)
    assert out.shape[:2] == (10, 10)


def test_trim_black_keeps_tiny_result():
    img = np.zeros((10, 10, 3), np.uint8)
    img[4:6, 4:6] = 200  # 裁完 < 8x8 → 原样返回
    out = R.trim_black(img, threshold=22, min_keep=0.5)
    assert out.shape[:2] == (10, 10)


def test_detect_h5_canvas_square_map_right():
    img = np.zeros((50, 50, 3), np.uint8)
    img[5:35, 5:45] = 150   # 画布 40 宽 30 高
    panel, map_rect, canvas = R.detect_h5_canvas(img)
    assert canvas == (5, 5, 40, 30)
    assert map_rect == (15, 5, 30, 30)   # 地图边长 = min(40,30)=30，贴右
    assert panel == (5, 5, 10, 30)


def test_detect_h5_canvas_all_black_is_none():
    img = np.zeros((20, 20, 3), np.uint8)
    assert R.detect_h5_canvas(img) == (None, None, None)
