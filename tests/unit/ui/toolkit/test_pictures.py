"""截图落盘单元测试（`chaita/ui/toolkit/pictures.py`）。

真值来自规则：空图不落盘、路径用 temp 目录 + 进程前缀、缩略图只缩不放。
cv2 / tempfile / 文件 I/O 全 stub。
"""

import numpy as np

import chaita.ui.toolkit.pictures as pic


def test_save_temp_none_is_empty():
    assert pic._save_temp(None, "x") == ""


def test_save_temp_writes_and_returns_url(monkeypatch):
    """测什么：真的把字节写进 temp 下那个文件，返回 file:// URL。

    （现在是 `imencode` + 自己写文件：`imwrite` 遇到非 ASCII 路径会静默失败，
    界面拿到坏 URL 就是个空框 —— 见 `_save_temp` 的注释。）
    """
    import tempfile
    import cv2
    monkeypatch.setattr(tempfile, "gettempdir", lambda: "TMP")
    monkeypatch.setattr(pic.os, "makedirs", lambda *a, **k: None)
    encoded = []

    class FakeBuffer(bytes):
        def tobytes(self):
            return bytes(self)

    monkeypatch.setattr(cv2, "imencode",
                        lambda ext, img: (encoded.append(ext),
                                          (True, FakeBuffer(b"png")))[1])
    written = []

    class FakeFile:
        def __init__(self, path, mode):
            written.append(path)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def write(self, data):
            written.append(len(data))

    monkeypatch.setattr(pic, "open", FakeFile, raising=False)
    url = pic._save_temp(object(), "mon_1")
    assert url.startswith("file:///")
    assert "mon_1.png" in url
    assert encoded == [".png"]
    assert written[0].replace("\\", "/").startswith("TMP/chaita/")
    assert written[1] == 3          # b"png" 三个字节


def test_save_temp_returns_empty_when_encode_or_write_fails(monkeypatch):
    """测什么：编码失败 / 写文件失败都返回空串，**不给界面一个打不开的 URL**。"""
    import tempfile
    import cv2
    monkeypatch.setattr(tempfile, "gettempdir", lambda: "TMP")
    monkeypatch.setattr(pic.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(cv2, "imencode", lambda ext, img: (False, b""))
    assert pic._save_temp(object(), "x") == ""

    monkeypatch.setattr(cv2, "imencode", lambda ext, img: (True, b"png"))

    def boom(path, mode):
        raise OSError("没有权限")

    monkeypatch.setattr(pic, "open", boom, raising=False)
    assert pic._save_temp(object(), "x") == ""


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
