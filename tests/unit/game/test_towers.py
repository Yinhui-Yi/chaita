"""塔描述与区域解析单元测试（`chaita/game/towers.py`）。

真值来自规则：塔表只有 rm/h5 两座、固定布局按参考尺寸缩放后切、h5 交给自动检测。
"""

import numpy as np

import chaita.game.towers as T


def test_towers_registry():
    assert set(T.TOWERS) == {"rm", "h5"}
    assert T.TOWERS["rm"].layout == T.LAYOUT_FIXED
    assert T.TOWERS["h5"].layout == T.LAYOUT_H5_AUTO


def test_tower_str_has_key_and_process():
    text = str(T.RM_TUTORIAL)
    assert "rm" in text
    assert "game.exe" in text


def test_resolve_fixed_no_resize_when_matching():
    tower = T.RM_TUTORIAL
    img = np.zeros((764, 969, 3), np.uint8)  # 参考尺寸
    panel, map_rect, normalized = T.resolve(tower, img)
    assert panel == (0, 28, 163, 478)
    assert map_rect == (163, 28, 483, 478)
    assert normalized is img


def test_resolve_fixed_resizes_to_ref():
    tower = T.RM_TUTORIAL
    img = np.zeros((382, 484, 3), np.uint8)  # 一半大小 → 缩到参考尺寸
    panel, map_rect, normalized = T.resolve(tower, img)
    assert normalized.shape[:2] == (764, 969)


def test_resolve_h5_auto_uses_detector(monkeypatch):
    import chaita.game.regions as R
    monkeypatch.setattr(R, "detect_h5_canvas",
                        lambda img: ((1, 2, 3, 4), (5, 6, 7, 8), img))
    img = np.zeros((10, 10, 3), np.uint8)
    panel, map_rect, normalized = T.resolve(T.H5_MOTA, img)
    assert panel == (1, 2, 3, 4)
    assert map_rect == (5, 6, 7, 8)
    assert normalized is img


def test_resolve_h5_no_canvas_raises(monkeypatch):
    import pytest

    import chaita.game.regions as R
    monkeypatch.setattr(R, "detect_h5_canvas", lambda img: (None, None, None))
    img = np.zeros((10, 10, 3), np.uint8)
    with pytest.raises(RuntimeError):
        T.resolve(T.H5_MOTA, img)
