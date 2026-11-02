"""图像工具：给模型看的放大裁剪（look）、按比例框裁图标（crop_box）、抠图（crop_cutout）。

怪物图标：框准了裁出来，再用 rembg 把底纹抠掉（白色边框由 AI 框的时候就排除在外）。
没有抠图模型时退回直接裁的截图。不碰模型调用。
"""

import json
import os
import threading
import time

import cv2
import numpy as np

from agent_framework import Content, tool

from ... import trace
from .core import png


def _crop_ratio(image, x, y, w, h):
    """按比例框裁原图。不缩放、不补边，裁出来什么样就什么样。"""
    if image is None or getattr(image, "size", 0) == 0:
        return None
    height, width = image.shape[:2]
    try:
        left, top = float(x), float(y)
        box_w, box_h = float(w), float(h)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= left < 1.0 and 0.0 <= top < 1.0
            and 0.0 < box_w <= 1.0 and 0.0 < box_h <= 1.0):
        return None
    x0, y0 = int(round(left * width)), int(round(top * height))
    x1 = int(round(min(1.0, left + box_w) * width))
    y1 = int(round(min(1.0, top + box_h) * height))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return image[y0:y1, x0:x1]


def crop_box(image, box):
    """按 box（0~1 比例，{x,y,w,h}）裁出一份独立的图；box 不合法返回 None。"""
    if not isinstance(box, dict):
        return None
    crop = _crop_ratio(image, box.get("x"), box.get("y"),
                       box.get("w"), box.get("h"))
    return None if crop is None else crop.copy()


# ---- 抠图（rembg / u2net）：把怪物从格子底纹里分出来 ----

_REMBG_SESSIONS = {}
_REMBG_LOCK = threading.Lock()
_REMBG_MODEL = "u2net.onnx"
# 模型给的是软 alpha（边缘一圈半透明、浅色怪周围还有一层雾）。像素风小怪要锐利：
# 一刀切成要 / 不要，雾（alpha 很低）就自然没了
_ALPHA_CUT = 127


def _rembg_home() -> str:
    """老版本 rembg 的模型缓存目录（rembg 自己认 `U2NET_HOME`，默认 `~/.u2net`）。"""
    home = os.environ.get("U2NET_HOME") or os.path.join(os.path.expanduser("~"),
                                                        ".u2net")
    if os.path.basename(home) != ".u2net":
        home = os.path.join(home, ".u2net")
    return home


def _model_ready() -> bool:
    """抠图模型在不在本地。

    **问 rembg 自己它把模型放哪**，别自己猜路径：rembg 2.0.8x 起放在
    `~/.rembg/models/u2net/`（`REMBG_HOME` / `U2NET_HOME` 也认），旧版放 `~/.u2net/`。
    `resolve_existing` 两处都找、而且不会下载。

    为什么非要先看这一眼：`new_session("u2net")` 在模型缺失时**会去下载**
    （约 176 MB）。实测下不动时 sprite 卡了 5 分钟以上一点动静都没有 —— 用户看到的就是
    「点了读怪物，界面没反应」。按钮不该触发下载，所以模型不在就退回不抠图的截图。
    想恢复抠图：`python -c "from rembg import new_session; new_session('u2net')"`
    跑一次（把模型缓存下来）。
    """
    try:
        from rembg.sessions.u2net import U2netSession
    except Exception:
        return False
    resolve = getattr(U2netSession, "resolve_existing", None)
    if resolve is None:
        # 老版本 rembg 没有这个接口：只能按它当年固定的目录找
        return os.path.exists(os.path.join(_rembg_home(), _REMBG_MODEL))
    return resolve(_REMBG_MODEL) is not None


def _rembg_session():
    """懒加载 rembg 会话（u2net）。有 CUDA 就用，没有自动退回 CPU。

    加锁：多只怪同时抠时不能各自建一个会话（实测重复建了 5 次，白花 25 秒）。
    """
    with _REMBG_LOCK:
        if "u2net" in _REMBG_SESSIONS:
            return _REMBG_SESSIONS["u2net"]
        from rembg import new_session

        providers = None
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
            providers = [name for name in ("CUDAExecutionProvider",
                                           "CPUExecutionProvider")
                         if name in available] or None
        except Exception as exc:
            trace.note("agent.ort_unavailable", error=repr(exc)[:120])
        started = time.time()
        session = new_session("u2net", providers=providers)
        trace.note("agent.rembg_ready", providers=providers,
                   seconds=round(time.time() - started, 1))
        _REMBG_SESSIONS["u2net"] = session
    return session


def _cutout(crop):
    """用 rembg(u2net) 把图案从底纹里抠出来，返回透明底的 BGRA（alpha 只有 0 / 255）。

    **不裁紧**：保持整块的原始尺寸，图案在格子里占多大就多大 ——
    "怪物图标的大小要和游戏里一致"：裁紧会让每只怪都填满整张图，小怪和大怪就一样大了。

    抠不了（模型不在 / 报错 / 前景太少）就原样返回这块图，宁可带一点底纹也不要空白；
    模型不在本地时**不去下载**（见 `_model_ready`）。
    """
    height, width = crop.shape[:2]
    plain = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    if height < 8 or width < 8:
        return plain
    if not _model_ready():
        trace.note("agent.cutout_no_model")
        return plain
    try:
        from rembg import remove
        rgba = remove(crop, session=_rembg_session())
    except Exception as exc:
        trace.note("agent.cutout_failed", error=repr(exc)[:200])
        return plain
    if rgba is None or getattr(rgba, "size", 0) == 0:
        return plain
    if rgba.shape[2] == 3:
        rgba = cv2.cvtColor(rgba, cv2.COLOR_BGR2BGRA)
    solid = rgba[:, :, 3] > _ALPHA_CUT
    foreground = float(solid.mean())
    if foreground < 0.02:
        trace.note("agent.cutout_empty", ratio=round(foreground, 3))
        return plain
    rgba = rgba.copy()
    rgba[:, :, 3] = np.where(solid, 255, 0).astype(np.uint8)
    trace.note("agent.cutout", ratio=round(foreground, 3),
               size=(width, height))
    return rgba


def crop_cutout(image, box):
    """按 box（0~1 比例，{x,y,w,h}）裁，再抠；box 不合法返回 None。"""
    crop = crop_box(image, box)
    return None if crop is None else _cutout(crop)


def look_tool(image, limit: int = 6):
    """look 是一个真正的工具：返回那一块的图片内容（官方 @tool + list[Content]）。

    `limit` 是**兜底上限**，不是让人省着用：正常一次读最多用 3 次，这里放到 6 次
    只是为了拦住病态循环。实测过一张缩略图把模型带进死循环：连调 17 次 look 都
    不收敛，7 分钟没出结果（只能手动掐）。有上限之后最坏也就是几个回合就收口。
    """
    used = {"count": 0}

    @tool(name="look",
          description="查看原图的某个区域，返回原图的这一块（不缩放、不做任何处理）。"
                      "参数 x,y,w,h 都是 0~1 的比例（左上角与宽高）。")
    def look(x: float, y: float, w: float, h: float) -> list:
        if used["count"] >= limit:
            trace.note("agent.look_capped", box=[x, y, w, h], limit=limit)
            return [Content.from_text(
                "本次已经看了 %d 块，不再给新区域了。请按你**已经看到**的内容"
                "直接作答；看不清的数字写 ???，不要再调用 look。" % limit)]
        used["count"] += 1
        crop = _crop_ratio(image, x, y, w, h)
        if crop is None:
            return [Content.from_text("这个框不合法（超出图片或太小），"
                                      "请用 0~1 比例重新给。")]
        trace.note("agent.look", box=[x, y, w, h],
                   size=(crop.shape[1], crop.shape[0]))
        return [
            Content.from_text("按你给的比例裁出来的图如下"
                              "（x=%s y=%s w=%s h=%s，比例仍相对原图）。"
                              % (x, y, w, h)),
            Content.from_data(data=png(crop), media_type="image/png"),
        ]

    return look


def collect_icons(response) -> dict:
    """从响应的 messages 里取图标：function_call 的 JSON 参数 → function_result 的图片。

    这样图标是**函数调用和它的返回值**带回来的，不是我本地存一份字典再拼给别人。
    """
    import base64

    names = {}
    icons = {}
    for message in getattr(response, "messages", []) or []:
        for content in getattr(message, "contents", []) or []:
            kind = str(getattr(content, "type", "") or "")
            if kind == "function_call":
                try:
                    args = json.loads(getattr(content, "arguments", "") or "{}")
                except Exception:
                    args = {}
                call_id = str(getattr(content, "call_id", "") or "")
                name = str(args.get("name", "") or "").strip()
                if call_id and name:
                    names[call_id] = name
            elif kind == "function_result":
                name = names.get(str(getattr(content, "call_id", "") or ""))
                if not name:
                    continue
                for inner in getattr(content, "items", []) or []:
                    if str(getattr(inner, "media_type", "") or "") != "image/png":
                        continue
                    data = getattr(inner, "data", None) or b""
                    if not data:
                        uri = str(getattr(inner, "uri", "") or "")
                        if uri.startswith("data:") and "," in uri:
                            try:
                                data = base64.b64decode(uri.split(",", 1)[1])
                            except Exception:
                                data = b""
                    if not data:
                        continue
                    icon = cv2.imdecode(np.frombuffer(data, np.uint8),
                                        cv2.IMREAD_UNCHANGED)
                    if icon is not None and icon.size:
                        icons[name] = icon
    trace.note("agent.collect_icons", names=list(icons)[:20])
    return icons
