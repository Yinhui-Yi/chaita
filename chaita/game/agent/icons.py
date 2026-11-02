"""图像工具：给模型看的放大裁剪（look）和按比例框裁图标（crop_box）。不碰模型调用。

怪物图标**不再抠图**（用户 2026-11-02："不一定要抠图，截图也行"）：框准了，
直接裁那一整格就是图标，没有模型、没有半透明雾、也不依赖本机装没装 rembg。
"""

import json

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
