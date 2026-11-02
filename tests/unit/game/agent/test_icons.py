"""图像工具单元测试（`chaita/game/agent/icons.py`）。

真值来自规则：比例框不缩放不补边、框不合法/太小返回 None、
crop_box 裁出独立的一份、抠图保持原尺寸且 alpha 只有 0/255、抠不了就退回截图、
模型在哪问 rembg 自己、collect_icons 按 call_id 把名字和图标对上。
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


# ---- 抠图：模型在哪 / 抠不了就退回截图 / alpha 只有 0 和 255 ----

def _quiet(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def _fake_u2net_session(monkeypatch, resolve):
    """把 `rembg.sessions.u2net.U2netSession` 换成只会回答"模型在哪"的假货。"""
    import sys
    import types
    session = types.SimpleNamespace(
        U2netSession=types.SimpleNamespace(resolve_existing=resolve))
    monkeypatch.setitem(sys.modules, "rembg.sessions.u2net", session)


def test_model_ready_问rembg自己模型放在哪_而不是猜路径(monkeypatch):
    """rembg 2.0.8x 把模型放在 ~/.rembg/models/u2net/，旧版放 ~/.u2net/：
    本机 u2net.onnx 就在前者，按旧路径找会一直"没有模型"、永远不抠。"""
    asked = []
    _fake_u2net_session(
        monkeypatch,
        lambda fname: asked.append(fname) or r"C:\Users\x\.rembg\models\u2net\u2net.onnx")
    monkeypatch.setattr(ic, "_rembg_home", lambda: "/nowhere/.u2net")
    monkeypatch.setattr(ic.os.path, "exists", lambda p: False)

    assert ic._model_ready() is True
    assert asked == ["u2net.onnx"]


def test_model_not_ready_rembg说没有就是没有(monkeypatch):
    _fake_u2net_session(monkeypatch, lambda fname: None)
    monkeypatch.setattr(ic.os.path, "exists", lambda p: True)   # 旧路径有也不算

    assert ic._model_ready() is False


def test_model_ready_老版本rembg没有resolve_existing_退回看旧目录(monkeypatch):
    import sys
    import types
    monkeypatch.setitem(sys.modules, "rembg.sessions.u2net",
                        types.SimpleNamespace(U2netSession=types.SimpleNamespace()))
    monkeypatch.setattr(ic, "_rembg_home", lambda: "/home/.u2net")
    monkeypatch.setattr(ic.os.path, "exists", lambda p: p.endswith("u2net.onnx"))
    assert ic._model_ready() is True

    monkeypatch.setattr(ic.os.path, "exists", lambda p: False)
    assert ic._model_ready() is False


def test_model_ready_rembg导不进来就当没有(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "rembg.sessions.u2net", None)   # import 会抛 ImportError
    assert ic._model_ready() is False


def test_rembg_home_env_with_dot_u2net(monkeypatch):
    monkeypatch.setenv("U2NET_HOME", "/some/.u2net")
    assert ic._rembg_home().endswith(".u2net")


def test_rembg_home_appends_dot_u2net(monkeypatch):
    monkeypatch.setenv("U2NET_HOME", "/some/foo")
    assert ic._rembg_home().endswith(".u2net")


def _stub_rembg(monkeypatch, remove_fn):
    import sys
    import types
    fake = types.ModuleType("rembg")
    fake.remove = remove_fn
    monkeypatch.setitem(sys.modules, "rembg", fake)
    monkeypatch.setattr(ic, "_model_ready", lambda: True)
    monkeypatch.setattr(ic, "_rembg_session", lambda: object())
    _quiet(monkeypatch)


def _crop(size=10):
    return np.full((size, size, 3), 50, np.uint8)


def test_cutout_太小的图直接转BGRA():
    assert ic._cutout(np.zeros((4, 4, 3), np.uint8)).shape == (4, 4, 4)


def test_cutout_没有模型就退回不抠的截图_完全不透明(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(ic, "_model_ready", lambda: False)

    out = ic._cutout(_crop())

    assert out.shape == (10, 10, 4)
    assert (out[:, :, 3] == 255).all()
    assert (out[:, :, :3] == 50).all()


def test_cutout_模型报错_返回空结果_前景太少_都退回截图(monkeypatch):
    for remove in (lambda crop, session=None: (_ for _ in ()).throw(Exception("boom")),
                   lambda crop, session=None: None,
                   lambda crop, session=None: np.zeros((10, 10, 4), np.uint8)):
        _stub_rembg(monkeypatch, remove)
        out = ic._cutout(_crop())
        assert out.shape == (10, 10, 4)
        assert (out[:, :, 3] == 255).all()        # 宁可带底纹也不要空白


def test_cutout_三通道的结果也转成BGRA(monkeypatch):
    _stub_rembg(monkeypatch, lambda crop, session=None: np.zeros((10, 10, 3), np.uint8))
    assert ic._cutout(_crop()).shape[2] == 4


def test_cutout_alpha只留0和255_软边和雾都被切掉(monkeypatch):
    soft = np.zeros((10, 10, 4), np.uint8)
    soft[:, :, 3] = np.tile(np.array([0, 30, 100, 126, 128, 200, 255, 255, 255, 255],
                                     np.uint8), (10, 1))
    _stub_rembg(monkeypatch, lambda crop, session=None: soft)

    out = ic._cutout(_crop())

    assert set(np.unique(out[:, :, 3]).tolist()) == {0, 255}
    assert (out[:, :, 3][:, :4] == 0).all()       # ≤127（雾 / 半透明）不要
    assert (out[:, :, 3][:, 4:] == 255).all()


def test_cutout_保持原尺寸_不裁紧(monkeypatch):
    """怪物图标的大小要和游戏里一致：小怪和大怪抠完整块一样大。"""
    mask = np.zeros((10, 10, 4), np.uint8)
    mask[4:6, 4:6, 3] = 255
    _stub_rembg(monkeypatch, lambda crop, session=None: mask)

    assert ic._cutout(_crop()).shape == (10, 10, 4)


def test_crop_cutout_框不合法是None_合法就裁了再抠(monkeypatch):
    img = np.zeros((20, 20, 3), np.uint8)
    assert ic.crop_cutout(None, {"x": 0, "y": 0, "w": 1, "h": 1}) is None
    assert ic.crop_cutout(img, "not dict") is None
    assert ic.crop_cutout(img, {"x": 2, "y": 0, "w": 0.5, "h": 0.5}) is None

    monkeypatch.setattr(ic, "_cutout", lambda crop: ("CUT", crop.shape[:2]))
    assert ic.crop_cutout(img, {"x": 0, "y": 0, "w": 0.5, "h": 0.5}) == ("CUT", (10, 10))


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
    monkeypatch.setattr(ic, "_REMBG_SESSIONS", {})
    return made


def test_rembg_session只建一次_有哪个provider就带哪个(monkeypatch):
    _quiet(monkeypatch)
    made = _fake_rembg(monkeypatch, providers=["CPUExecutionProvider"])

    assert ic._rembg_session() == "SESSION"
    assert ic._rembg_session() == "SESSION"     # 第二次直接用缓存
    assert made == [("u2net", ["CPUExecutionProvider"])]


def test_rembg_session_没装onnxruntime就不传provider(monkeypatch):
    _quiet(monkeypatch)
    made = _fake_rembg(monkeypatch, providers=None)

    assert ic._rembg_session() == "SESSION"
    assert made == [("u2net", None)]


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
