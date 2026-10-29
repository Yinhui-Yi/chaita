"""截图落盘单元测试（`chaita/ui/toolkit/pictures.py`）。

真值来自规则：空图不落盘、路径用 temp 目录 + 进程前缀、缩略图只缩不放。
cv2 / tempfile / 文件 I/O 全 stub。
"""

import numpy as np

import chaita.ui.toolkit.pictures as pic


def test_save_temp_none_is_empty():
    assert pic._save_temp(None, "x") == ""


def test_save_temp_writes_and_returns_url(monkeypatch):
    import tempfile
    import cv2
    monkeypatch.setattr(tempfile, "gettempdir", lambda: "TMP")
    monkeypatch.setattr(pic.os, "makedirs", lambda *a, **k: None)
    written = []
    monkeypatch.setattr(cv2, "imwrite",
                        lambda path, img: written.append(path))
    url = pic._save_temp(object(), "mon_1")
    assert url.startswith("file:///")
    assert "mon_1.png" in url
    assert len(written) == 1
    assert written[0].replace("\\", "/").startswith("TMP/chaita/")


def test_save_thumb_none_or_empty_is_empty():
    assert pic._save_thumb(None, "x") == ""
    empty = np.zeros((0, 0, 3), np.uint8)
    assert pic._save_thumb(empty, "x") == ""


def test_save_thumb_resizes_only_when_wider(monkeypatch):
    import cv2
    resized = []
    monkeypatch.setattr(cv2, "resize",
                        lambda b, size, interpolation:
                        (resized.append(size), b)[1])
    monkeypatch.setattr(pic, "_save_temp", lambda b, stem: "file:///x")
    # 宽 300 > 150 → 缩
    wide = np.zeros((100, 300, 3), np.uint8)
    assert pic._save_thumb(wide, "t", 150) == "file:///x"
    assert resized and resized[-1][0] == 150
    # 宽 100 < 150 → 不缩（只缩不放）
    narrow = np.zeros((100, 100, 3), np.uint8)
    resized.clear()
    pic._save_thumb(narrow, "t", 150)
    assert resized == []
