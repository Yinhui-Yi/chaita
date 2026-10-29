"""图像工具单元测试（`chaita/game/agent/icons.py`）。

真值来自规则：模型目录固定 .u2net、比例框不缩放不补边、框不合法/太小返回 None、
collect_icons 按 call_id 把名字和图标对上。
"""

import numpy as np

import chaita.game.agent.icons as ic


def test_rembg_home_env_with_dot_u2net(monkeypatch):
    monkeypatch.setenv("U2NET_HOME", "/some/.u2net")
    assert ic._rembg_home().endswith(".u2net")


def test_rembg_home_appends_dot_u2net(monkeypatch):
    monkeypatch.setenv("U2NET_HOME", "/some/foo")
    assert ic._rembg_home().endswith(".u2net")


def test_model_ready(monkeypatch):
    monkeypatch.setattr(ic, "_rembg_home", lambda: "/home/.u2net")
    monkeypatch.setattr(ic.os.path, "exists", lambda p: True)
    assert ic._model_ready() is True


def test_model_not_ready(monkeypatch):
    monkeypatch.setattr(ic, "_rembg_home", lambda: "/home/.u2net")
    monkeypatch.setattr(ic.os.path, "exists", lambda p: False)
    assert ic._model_ready() is False


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


def test_refine_alpha_small_returns_as_is():
    rgba = np.zeros((5, 5, 4), np.uint8)
    crop = np.zeros((5, 5, 3), np.uint8)
    assert ic._refine_alpha(rgba, crop) is rgba


def test_collect_icons_matches_call_to_result(monkeypatch):
    import cv2
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)

    class Content:
        def __init__(self, type, arguments="", call_id="", items=None):
            self.type = type
            self.arguments = arguments
            self.call_id = call_id
            self.items = items or []

    class Inner:
        def __init__(self, media_type="", data=b""):
            self.media_type = media_type
            self.data = data

    class Msg:
        def __init__(self, contents):
            self.contents = contents

    class Resp:
        def __init__(self, messages):
            self.messages = messages

    buf = cv2.imencode(".png", np.zeros((1, 1, 3), np.uint8))[1].tobytes()
    resp = Resp([
        Msg([Content("function_call", arguments='{"name":"血蚊"}', call_id="c1")]),
        Msg([Content("function_result", call_id="c1",
                     items=[Inner("image/png", buf)])]),
    ])
    icons = ic.collect_icons(resp)
    assert "血蚊" in icons
    assert icons["血蚊"].size > 0


def test_cutout_small_returns_bgra():
    rgba = ic._cutout(np.zeros((4, 4, 3), np.uint8))  # < 8px 直接转 BGRA
    assert rgba.shape[2] == 4


def test_cutout_no_model_returns_bgra(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    monkeypatch.setattr(ic, "_model_ready", lambda: False)
    rgba = ic._cutout(np.zeros((10, 10, 3), np.uint8))
    assert rgba.shape[2] == 4


def _stub_rembg(monkeypatch, remove_fn):
    import sys
    import types

    import chaita.trace as trace
    fake = types.ModuleType("rembg")
    fake.remove = remove_fn
    monkeypatch.setitem(sys.modules, "rembg", fake)
    monkeypatch.setattr(ic, "_model_ready", lambda: True)
    monkeypatch.setattr(ic, "_rembg_session", lambda: object())
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def test_cutout_remove_fails_returns_bgra(monkeypatch):
    _stub_rembg(monkeypatch,
                lambda crop, session=None: (_ for _ in ()).throw(
                    Exception("boom")))
    assert ic._cutout(np.zeros((10, 10, 3), np.uint8)).shape[2] == 4


def test_cutout_remove_none_returns_bgra(monkeypatch):
    _stub_rembg(monkeypatch, lambda crop, session=None: None)
    assert ic._cutout(np.zeros((10, 10, 3), np.uint8)).shape[2] == 4


def test_cutout_low_foreground_returns_bgra(monkeypatch):
    rgba = np.zeros((10, 10, 4), np.uint8)   # alpha 全 0 → 前景 0
    _stub_rembg(monkeypatch, lambda crop, session=None: rgba)
    assert ic._cutout(np.zeros((10, 10, 3), np.uint8)).shape[2] == 4


def test_cutout_3channel_becomes_bgra(monkeypatch):
    bgr = np.zeros((10, 10, 3), np.uint8)
    _stub_rembg(monkeypatch, lambda crop, session=None: bgr)
    assert ic._cutout(np.zeros((10, 10, 3), np.uint8)).shape[2] == 4


def test_crop_cutout_invalid_box(monkeypatch):
    img = np.zeros((10, 10, 3), np.uint8)
    assert ic.crop_cutout(None, {"x": 0, "y": 0, "w": 1, "h": 1}) is None
    assert ic.crop_cutout(img, "not dict") is None
    assert ic.crop_cutout(img, {"x": 2, "y": 0, "w": 0.5, "h": 0.5}) is None


def test_crop_cutout_valid(monkeypatch):
    monkeypatch.setattr(ic, "_cutout", lambda crop: "CUT")
    img = np.zeros((100, 100, 3), np.uint8)
    assert ic.crop_cutout(img, {"x": 0, "y": 0, "w": 1, "h": 1}) == "CUT"


# ---- _refine_alpha：只挖"从四边连通"的底色，删太多就整个撤销 ----

def _crop_with_ring(interior=200, ring=20, size=64, thick=4):
    """外圈 `thick` 像素是底色、里面是图案。

    `thick` 要 >= 函数自己取的边圈宽度（`max(2, min(4, size//12))`），
    否则取底色时会把图案的颜色也取进去，整张图都会被判成"底色"。
    """
    crop = np.full((size, size, 3), interior, np.uint8)
    crop[:thick, :] = ring
    crop[-thick:, :] = ring
    crop[:, :thick] = ring
    crop[:, -thick:] = ring
    return crop


def _rgba(crop):
    alpha = np.full(crop.shape[:2], 255, np.uint8)
    return np.dstack([crop, alpha])


def test_refine_alpha_removes_edge_connected_background(monkeypatch):
    _quiet_trace(monkeypatch)
    crop = _crop_with_ring()
    rgba = _rgba(crop)

    out = ic._refine_alpha(rgba, crop)

    assert out.shape == rgba.shape            # 只改 alpha，不改尺寸
    assert out[0, 0, 3] == 0                  # 贴着四边的底色被挖掉
    assert out[-1, -1, 3] == 0
    assert out[32, 32, 3] == 255              # 中间图案留着


def test_refine_alpha_keeps_interior_same_color(monkeypatch):
    """图案内部和底色同色、但不连到边 —— 不许挖（否则浅色图案会被戳空）。"""
    _quiet_trace(monkeypatch)
    crop = _crop_with_ring()
    crop[30:34, 30:34] = 20                   # 内部一小块同色
    rgba = _rgba(crop)

    out = ic._refine_alpha(rgba, crop)

    assert out[31, 31, 3] == 255              # 内部同色块保住了
    assert out[0, 0, 3] == 0                  # 边缘那块照样挖掉


def test_refine_alpha_undoes_when_removing_too_much(monkeypatch):
    """删掉 25% 以上说明把图案当背景挖了：整个精修撤销，保留 rembg 的结果。"""
    notes = []
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note",
                        lambda event, **kw: notes.append(event))
    crop = np.full((40, 40, 3), 20, np.uint8)  # 整张都是底色
    rgba = _rgba(crop)

    out = ic._refine_alpha(rgba, crop)

    assert out is rgba                         # 原样返回
    assert "agent.refine_skip" in notes


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


# ---- rembg 会话：只建一次、有 CUDA 就带上 ----

def _fake_rembg(monkeypatch, providers=None):
    import sys
    import types
    made = []
    fake = types.ModuleType("rembg")

    def new_session(name, providers=None):
        made.append((name, providers))
        return "SESSION"

    fake.new_session = new_session
    monkeypatch.setitem(sys.modules, "rembg", fake)
    if providers is None:
        monkeypatch.setitem(sys.modules, "onnxruntime", None)
    else:
        ort = types.ModuleType("onnxruntime")
        ort.get_available_providers = lambda: list(providers)
        monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setattr(ic, "_REMBG_SESSION", None)
    monkeypatch.setattr(ic, "_REMBG_LOCK", None)
    return made


def test_rembg_session_builds_once_with_available_provider(monkeypatch):
    _quiet_trace(monkeypatch)
    made = _fake_rembg(monkeypatch, providers=["CPUExecutionProvider"])

    assert ic._rembg_session() == "SESSION"
    assert ic._rembg_session() == "SESSION"     # 第二次直接用缓存
    assert made == [("u2net", ["CPUExecutionProvider"])]


def test_rembg_session_without_onnxruntime_passes_none(monkeypatch):
    _quiet_trace(monkeypatch)
    made = _fake_rembg(monkeypatch, providers=None)

    assert ic._rembg_session() == "SESSION"
    assert made == [("u2net", None)]


# ---- collect_icons 的边角：坏 JSON / 对不上名字 / 不是 png / data-uri ----

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


def test_collect_icons_survives_bad_arguments_json(monkeypatch):
    _quiet_trace(monkeypatch)
    buf = __import__("cv2").imencode(
        ".png", np.zeros((1, 1, 3), np.uint8))[1].tobytes()
    resp = _Resp([
        _Msg([_Content("function_call", arguments="不是 json", call_id="c1")]),
        _Msg([_Content("function_result", call_id="c1",
                       items=[_Inner("image/png", buf)])]),
    ])
    # 参数解析不出来 → 不知道这次是谁的图 → 丢掉，但不炸
    assert ic.collect_icons(resp) == {}


def test_collect_icons_skips_result_without_matching_call(monkeypatch):
    _quiet_trace(monkeypatch)
    buf = __import__("cv2").imencode(
        ".png", np.zeros((1, 1, 3), np.uint8))[1].tobytes()
    resp = _Resp([_Msg([_Content("function_result", call_id="没有这个",
                                 items=[_Inner("image/png", buf)])])])
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
    import cv2
    buf = cv2.imencode(".png", np.zeros((2, 2, 3), np.uint8))[1].tobytes()
    uri = "data:image/png;base64," + base64.b64encode(buf).decode()
    resp = _Resp([
        _Msg([_Content("function_call", arguments='{"name":"铁卫"}',
                       call_id="c9")]),
        _Msg([_Content("function_result", call_id="c9",
                       items=[_Inner("image/png", b"", uri)])]),
    ])

    icons = ic.collect_icons(resp)

    assert "铁卫" in icons
    assert icons["铁卫"].size > 0
