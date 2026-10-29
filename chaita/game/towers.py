"""塔描述。

实测结论：不同塔的 UI 差别很大，但可以分成两类处理。

**固定布局（RMXP 教程塔）**：黑底状态栏贴左边、地图占右侧，画布本身没有边框，
外面套着一个窗口标题栏。坐标写死，量一次即可。

**h5 魔塔（h5mota）**：页面黑底上居中一块画布，画布内左侧面板 + 右侧地图。
实测喵塔和 cxd_imprisoned 两座界面完全不同，但结构一致（面板约占画布宽 24%、
地图是正方形），所以不必写死坐标 —— 用 `regions.detect_h5_canvas()` 自动找。
窗口缩放、换一座同结构的塔，都不用重新标定。

字段清单不放在这里：塔之间的字段差异由提示词里的"可能出现的字段"覆盖，见 `read.py`。
"""

from dataclasses import dataclass

# 布局类型
LAYOUT_FIXED = "fixed"
LAYOUT_H5_AUTO = "h5auto"


@dataclass
class Tower:
    key: str
    name: str
    # 找窗口用的进程名（小写）。按进程匹配比按标题稳：标题会变，
    # 而且实测 Edge 标题里夹着零宽字符，前缀匹配会失败。
    process: str
    layout: str = LAYOUT_FIXED
    # ---- 以下仅 LAYOUT_FIXED 使用 ----
    # 抓图里要跳过的顶部像素（窗口标题栏）
    top_skip: int = 0
    # 参考尺寸 (宽, 高)。区域坐标按这个尺寸量，抓图先缩放到它再切 ——
    # 实测窗口缩放后 PrintWindow 的输出尺寸会跟着变。
    ref_size: tuple = (0, 0)
    panel: tuple = (0, 0, 0, 0)
    map: tuple = (0, 0, 0, 0)
    # 校验用：地图区平均亮度合理区间与最低内容起伏。
    # 浏览器窗口里可能是任意页面（实测抓到过文档站），不校验就白烧一次调用。
    canvas_bright: tuple = None
    min_std: float = 8.0

    def __str__(self) -> str:
        return "%s(%s, 进程=%s)" % (self.name, self.key, self.process)


# RMXP 教程塔：按 969x764 参考尺寸量（PrintWindow 输出的最大尺寸）
# 实测：内容 646x506 在左上角，面板/地图分界 x=163
RM_TUTORIAL = Tower(
    key="rm",
    name="教程塔（RMXP）",
    process="game.exe",
    layout=LAYOUT_FIXED,
    top_skip=28,
    ref_size=(969, 764),
    panel=(0, 28, 163, 478),
    map=(163, 28, 483, 478),
    canvas_bright=(0, 200),
)

# h5mota：区域自动检测，不写死坐标。
# 同一浏览器窗口里换游戏（喵塔 → cxd_imprisoned）不用改任何配置。
H5_MOTA = Tower(
    key="h5",
    name="h5mota 魔塔",
    process="msedge.exe",
    layout=LAYOUT_H5_AUTO,
    canvas_bright=(20, 220),
)

TOWERS = {t.key: t for t in (RM_TUTORIAL, H5_MOTA)}


def resolve(tower: Tower, image):
    """返回 (panel_rect, map_rect, normalized_image)。

    LAYOUT_FIXED：先缩放到参考尺寸，再按量好的绝对矩形切。
    LAYOUT_H5_AUTO：自动找画布，按比例切。
    """
    import cv2

    from . import regions as R

    if tower.layout == LAYOUT_H5_AUTO:
        panel, map_rect, _canvas = R.detect_h5_canvas(image)
        if panel is None:
            raise RuntimeError("没找到游戏画布（页面里可能没打开游戏）")
        return panel, map_rect, image

    ref_w, ref_h = tower.ref_size
    height, width = image.shape[:2]
    if (width, height) != (ref_w, ref_h):
        normalized = cv2.resize(image, (ref_w, ref_h),
                                interpolation=cv2.INTER_AREA)
    else:
        normalized = image

    def rect(spec):
        x, y, w, h = spec
        x = max(0, min(ref_w - 1, int(x)))
        y = max(0, min(ref_h - 1, int(y)))
        w = max(1, min(ref_w - x, int(w)))
        h = max(1, min(ref_h - y, int(h)))
        return (x, y, w, h)

    return rect(tower.panel), rect(tower.map), normalized

