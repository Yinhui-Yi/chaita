"""截图落盘：临时大图与列表缩略图。"""

import os

from ..constants import _SESSION


def _save_temp(bgr, path_stem: str) -> str:
    """把 BGR 数组存成临时图片，返回 file:// URL。

    QML 的 Image.source 只接受 URL，直接传 QImage 会报
    "Unable to assign QImage to QUrl"，所以落盘再传路径。

    path_stem 必须每次不同，而且**跨进程唯一**。以前只带序号（seq / frame），
    这两个计数器每次启动都从 0 开始，重启后生成的文件名和上一次完全一样：
    temp 里那张旧图被新图覆盖，界面上"一开始截的怪物手册"就变成了地图。
    现在统一加一个进程启动时间戳前缀，重启不会撞名。
    """
    import tempfile

    import cv2
    if bgr is None:
        return ""
    directory = os.path.join(tempfile.gettempdir(), "chaita")
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        return ""
    path = os.path.join(directory, "%s_%s.png" % (_SESSION, path_stem))
    # 先编码再自己写字节：`cv2.imwrite` 遇到非 ASCII 路径会**静默失败**（返回 False，
    # 但文件根本没写），界面那边拿到一个 file:// URL 却打不开图，看起来就是
    # "读取记录里没有缩略图"（用户 2026-10-31）。写不成一律返回空串，
    # 让调用方知道没有图，别塞一个坏 URL 进去。
    ok, buffer = cv2.imencode(".png", bgr)
    if not ok:
        return ""
    try:
        with open(path, "wb") as handle:
            handle.write(buffer.tobytes())
    except OSError:
        return ""
    return "file:///" + path.replace("\\", "/")

def _save_thumb(bgr, stem: str, width: int = 150) -> str:
    """把截图缩成缩略图存盘，返回 file:// URL；任务队列每行左边显示它。

    只缩不放，避免小图被放大成马赛克。
    """
    if bgr is None or getattr(bgr, "size", 0) == 0:
        return ""
    import cv2

    height, real_width = bgr.shape[:2]
    if real_width <= 0 or height <= 0:
        return ""
    scale = min(1.0, width / float(real_width))
    if scale < 1.0:
        size = (max(1, int(real_width * scale)), max(1, int(height * scale)))
        bgr = cv2.resize(bgr, size, interpolation=cv2.INTER_AREA)
    return _save_temp(bgr, stem)
