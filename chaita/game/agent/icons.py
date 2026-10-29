"""图像工具：给模型看的放大裁剪（look）和抠图（sprite）。不碰模型调用。"""

import json
import os
import threading
import time

import cv2
import numpy as np

from agent_framework import Content, tool

from ... import trace
from .core import png

_REMBG_SESSION = None
_REMBG_LOCK = None
_REMBG_MODEL = "u2net.onnx"


def _rembg_home() -> str:
    """rembg 的模型缓存目录（rembg 自己认 `U2NET_HOME`，默认 `~/.u2net`）。"""
    home = os.environ.get("U2NET_HOME") or os.path.join(os.path.expanduser("~"),
                                                        ".u2net")
    if os.path.basename(home) != ".u2net":
        home = os.path.join(home, ".u2net")
    return home


def _model_ready() -> bool:
    """抠图模型在不在本地。

    为什么非要先看这一眼：`new_session("u2net")` 在模型缺失时**会去下载**
    （约 176 MB）。这台机器上 `~/.u2net` 不存在时实测 sprite 卡了 5 分钟以上
    一点动静都没有 —— 用户看到的就是「点了读怪物，界面没反应」。
    按钮不该触发下载，所以模型不在就退回纯裁剪（宁可带一点背景）。
    想恢复干净抠图：`python -c "from rembg import new_session; new_session('u2net')"`
    跑一次（把模型缓存下来），或者把模型放到 `%USERPROFILE%\\.u2net\\u2net.onnx`。
    """
    return os.path.exists(os.path.join(_rembg_home(), _REMBG_MODEL))


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

def _rembg_session():
    """懒加载 rembg 会话：u2net 模型（实测能把这小图标单独分出来）。

    为什么用 u2net：
      · isnet-anime 在手册截图上完全失效（前景像素 0.0%）；
      · 传统做法（单色 / 调色板 / 纹理周期 / GrabCut）都留背景或把图案挖空；
      · u2net 五张图标全部干净、无背景、无边框（实测 1.6~1.8 秒/张，CPU）。
    有 CUDA 就用 CUDA，没有自动退回 CPU。加锁：多只怪同时调 sprite 时
    不能各自建一个会话（实测重复建了 5 次，白花 25 秒）。
    """
    global _REMBG_SESSION, _REMBG_LOCK
    import threading

    if _REMBG_LOCK is None:
        _REMBG_LOCK = threading.Lock()
    with _REMBG_LOCK:
        if _REMBG_SESSION is not None:
            return _REMBG_SESSION
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
        _REMBG_SESSION = new_session("u2net", providers=providers)
        trace.note("agent.rembg_ready", providers=providers,
                   seconds=round(time.time() - started, 1))
    return _REMBG_SESSION

def _refine_alpha(rgba, crop):
    """精修 alpha：把"贴着格子边缘、颜色又和格子底色一样"的残留去掉。

    rembg 有时会把一整片背景当成前景（骷髅人身后那一片、大蝙蝠上沿的暗边）。
    这里的判据很保守：
      · 底色取自格子外圈几像素（那圈必然是底纹/框线）；
      · 只有**从格子四边连通**的底色区才算残留；
      · 图案内部的同色不会被挖掉（不连通到边）。
    完全不改尺寸，只改 alpha。
    """
    alpha = (rgba[:, :, 3] > 40).astype(np.uint8)
    height, width = alpha.shape
    if height < 12 or width < 12:
        return rgba

    ring = max(2, min(4, min(height, width) // 12))
    border = np.concatenate([
        crop[:ring].reshape(-1, 3), crop[-ring:].reshape(-1, 3),
        crop[:, :ring].reshape(-1, 3), crop[:, -ring:].reshape(-1, 3),
    ]).astype(np.int16)
    quant = (border // 24)
    keys = quant[:, 0] * 4096 + quant[:, 1] * 64 + quant[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    palette_keys = set(values[np.argsort(counts)[-12:]].tolist())

    colors = crop.reshape(-1, 3).astype(np.int16)
    q = (colors // 24)
    pixel_keys = q[:, 0] * 4096 + q[:, 1] * 64 + q[:, 2]
    near = np.isin(pixel_keys, list(palette_keys)).reshape(height, width)

    count, labels = cv2.connectedComponents(near.astype(np.uint8), connectivity=8)
    edge = set(labels[0, :].tolist()) | set(labels[-1, :].tolist())
    edge |= set(labels[:, 0].tolist()) | set(labels[:, -1].tolist())
    edge.discard(0)
    residue = np.isin(labels, list(edge)) & near

    cleaned = alpha.copy()
    cleaned[residue] = 0

    # 去掉零碎小块（单像素噪点之类）
    count2, marks, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    if count2 > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        biggest = int(areas.max()) if areas.size else 0
        keep = [index + 1 for index, area in enumerate(areas)
                if area >= max(12, biggest * 0.02)]
        rebuilt = np.zeros_like(cleaned)
        for index in keep:
            rebuilt[marks == index] = 1
        if rebuilt.any():
            cleaned = rebuilt

    removed = int(alpha.sum() - cleaned.sum())
    total = int(alpha.sum())
    # 保护：删得太多说明这道精修把图案本身也当背景挖了（浅色图案容易中招），
    # 这种就整个撤销，保留 rembg 原来的结果。
    if total and removed > total * 0.25:
        trace.note("agent.refine_skip", removed=removed, total=total)
        return rgba
    trace.note("agent.refine", removed=removed, kept=int(cleaned.sum()))
    out = rgba.copy()
    out[:, :, 3] = (cleaned * 255).astype(np.uint8)
    return out

def _cutout(crop):
    """用 rembg(u2net) 把图案从花纹背景里抠出来，返回透明底的 RGBA。

    **不裁剪**：保持整块的原始尺寸，图案在格子里占多大就多大 ——
    这是"怪物图标的大小要和游戏里一致"的关键；裁紧会让每只怪都填满整张图，
    小怪和大怪看起来就一样大了。

    模型没分出来（前景太少）就原样返回这块图 —— 宁可带一点背景，也不要空白。
    模型不在本地时**不去下载**（见 `_model_ready`），直接给纯裁剪。
    """
    height, width = crop.shape[:2]
    if height < 8 or width < 8:
        return cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    if not _model_ready():
        trace.note("agent.cutout_no_model", home=_rembg_home())
        return cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    try:
        from rembg import remove
        rgba = remove(crop, session=_rembg_session())
    except Exception as exc:
        trace.note("agent.cutout_failed", error=repr(exc)[:200])
        return cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    if rgba is None or getattr(rgba, "size", 0) == 0:
        return cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    if rgba.shape[2] == 3:
        rgba = cv2.cvtColor(rgba, cv2.COLOR_BGR2BGRA)

    foreground = float((rgba[:, :, 3] > 40).mean())
    if foreground < 0.02:
        trace.note("agent.cutout_empty", ratio=round(foreground, 3))
        return cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)

    rgba = _refine_alpha(rgba, crop)

    rows = np.flatnonzero((rgba[:, :, 3] > 40).any(axis=1))
    cols = np.flatnonzero((rgba[:, :, 3] > 40).any(axis=0))
    coverage = ("%.2fx%.2f" % (
        (cols[-1] - cols[0] + 1) / float(width) if cols.size else 0.0,
        (rows[-1] - rows[0] + 1) / float(height) if rows.size else 0.0))
    trace.note("agent.cutout", ratio=round(foreground, 3),
               size=(width, height), coverage=coverage)
    return rgba

def crop_cutout(image, box):
    """按 box（0~1 比例，{x,y,w,h}）裁 + rembg 抠，返回 RGBA；box 不合法返回 None。

    方案 A 用它：模型把每只怪的 icon_box 当 JSON 文本交出来（不再调 sprite 工具），
    代码在这里一次裁完 —— 和 sprite 工具内部同一套 `_crop_ratio` + `_cutout`。
    """
    if not isinstance(box, dict):
        return None
    crop = _crop_ratio(image, box.get("x"), box.get("y"),
                       box.get("w"), box.get("h"))
    if crop is None:
        return None
    return _cutout(crop)

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
