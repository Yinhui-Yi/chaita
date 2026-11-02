"""图像工具单元测试（`chaita/game/agent/icons.py`）。

真值来自规则：比例框不缩放不补边、框不合法/太小返回 None、
crop_box 裁出独立的一份、collect_icons 按 call_id 把名字和图标对上。
（抠图已经整个拿掉：怪物图标直接裁整格截图。）
"""

import numpy as np

import chaita.game.agent.icons as ic


def test_crop_ratio_full():
    img = np.zeros((100, 200, 3), np.uint8)
    assert ic._crop_ratio(img, 0.0, 0.0, 1.0, 1.0).shape[:2] == (100, 200)


def test_crop_ratio_quarter():
    img = np.zeros((100, 200, 3), np.uint8)
    assert ic._crop_ratio(img, 0.5, 0.5, 0.5, 0.5).shape[:2] == (50, 100)


def test_crop_ratio_invalid_box():
    img = np.zeros((100, 200, 3), np.uint8)
    assert ic._crop_ratio(img, 2.0, 0.0, 0.5, 0.5) is None   # x 越界
    assert ic._crop_ratio(img, 0.0, 0.0, 0.01, 0.01) is None  # 太小


def test_crop_ratio_none_image():
    assert ic._crop_ratio(None, 0.0, 0.0, 1.0, 1.0) is None


# ---- crop_box：按比例框裁一份独立的图 ----

def test_crop_box_按框裁_不缩放():
    img = np.zeros((100, 200, 3), np.uint8)

    crop = ic.crop_box(img, {"x": 0.5, "y": 0.5, "w": 0.25, "h": 0.5})

    assert crop.shape[:2] == (50, 50)


def test_crop_box_裁出来的是独立的一份_改它不会动原图():
    img = np.zeros((100, 100, 3), np.uint8)

    crop = ic.crop_box(img, {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5})
    crop[:] = 255

    assert img.max() == 0


def test_crop_box_框不合法就是None():
    img = np.zeros((100, 100, 3), np.uint8)
    assert ic.crop_box(None, {"x": 0, "y": 0, "w": 1, "h": 1}) is None
    assert ic.crop_box(img, "not dict") is None
    assert ic.crop_box(img, None) is None
    assert ic.crop_box(img, {}) is None
    assert ic.crop_box(img, {"x": 2, "y": 0, "w": 0.5, "h": 0.5}) is None


# ---- look 工具：给图 + 有上限 + 框不合法要说清楚 ----

def _texts(items):
    out = []
    for item in items:
        for attr in ("text", "value", "content"):
            value = getattr(item, attr, None)
            if isinstance(value, str) and value:
                out.append(value)
                break
    return "\n".join(out)


def _quiet_trace(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def test_look_returns_text_and_image(monkeypatch):
    _quiet_trace(monkeypatch)
    img = np.zeros((100, 100, 3), np.uint8)
    look = ic.look_tool(img, limit=2)

    items = look(0.0, 0.0, 1.0, 1.0)

    assert len(items) == 2                     # 一句说明 + 一张 PNG
    assert "比例裁出来的图" in _texts(items)


def test_look_stops_at_the_limit(monkeypatch):
    """病态循环的兜底：用完次数就不再给新区域，让模型拿已有的内容作答。"""
    _quiet_trace(monkeypatch)
    img = np.zeros((100, 100, 3), np.uint8)
    look = ic.look_tool(img, limit=1)

    look(0.0, 0.0, 1.0, 1.0)
    items = look(0.0, 0.0, 1.0, 1.0)

    assert len(items) == 1
    assert "不再给新区域" in _texts(items)


def test_look_rejects_invalid_box(monkeypatch):
    _quiet_trace(monkeypatch)
    img = np.zeros((100, 100, 3), np.uint8)
    look = ic.look_tool(img, limit=1)

    items = look(2.0, 0.0, 0.5, 0.5)

    assert len(items) == 1
    assert "不合法" in _texts(items)


# ---- collect_icons：按 call_id 配对；坏 JSON / 对不上名字 / 不是 png / data-uri ----

class _Content:
    def __init__(self, type, arguments="", call_id="", items=None):
        self.type = type
        self.arguments = arguments
        self.call_id = call_id
        self.items = items or []


class _Inner:
    def __init__(self, media_type="", data=b"", uri=""):
        self.media_type = media_type
        self.data = data
        self.uri = uri


class _Msg:
    def __init__(self, contents):
        self.contents = contents


class _Resp:
    def __init__(self, messages):
        self.messages = messages


def _png_bytes(size=1):
    import cv2
    return cv2.imencode(".png", np.zeros((size, size, 3), np.uint8))[1].tobytes()


def test_collect_icons_matches_call_to_result(monkeypatch):
    _quiet_trace(monkeypatch)
    resp = _Resp([
        _Msg([_Content("function_call", arguments='{"name":"血蚊"}', call_id="c1")]),
        _Msg([_Content("function_result", call_id="c1",
                       items=[_Inner("image/png", _png_bytes())])]),
    ])

    icons = ic.collect_icons(resp)

    assert "血蚊" in icons
    assert icons["血蚊"].size > 0


def test_collect_icons_survives_bad_arguments_json(monkeypatch):
    _quiet_trace(monkeypatch)
    resp = _Resp([
        _Msg([_Content("function_call", arguments="不是 json", call_id="c1")]),
        _Msg([_Content("function_result", call_id="c1",
                       items=[_Inner("image/png", _png_bytes())])]),
    ])
    # 参数解析不出来 → 不知道这次是谁的图 → 丢掉，但不炸
    assert ic.collect_icons(resp) == {}


def test_collect_icons_skips_result_without_matching_call(monkeypatch):
    _quiet_trace(monkeypatch)
    resp = _Resp([_Msg([_Content("function_result", call_id="没有这个",
                                 items=[_Inner("image/png", _png_bytes())])])])
    assert ic.collect_icons(resp) == {}


def test_collect_icons_skips_non_png_and_empty(monkeypatch):
    _quiet_trace(monkeypatch)
    resp = _Resp([
        _Msg([_Content("function_call", arguments='{"name":"血蚊"}',
                       call_id="c1")]),
        _Msg([_Content("function_result", call_id="c1",
                       items=[_Inner("text/plain", b"x"),
                              _Inner("image/png", b"")])]),
    ])
    assert ic.collect_icons(resp) == {}


def test_collect_icons_accepts_data_uri(monkeypatch):
    _quiet_trace(monkeypatch)
    import base64
    uri = "data:image/png;base64," + base64.b64encode(_png_bytes(2)).decode()
    resp = _Resp([
        _Msg([_Content("function_call", arguments='{"name":"铁卫"}',
                       call_id="c9")]),
        _Msg([_Content("function_result", call_id="c9",
                       items=[_Inner("image/png", b"", uri)])]),
    ])

    icons = ic.collect_icons(resp)

    assert "铁卫" in icons
    assert icons["铁卫"].size > 0
