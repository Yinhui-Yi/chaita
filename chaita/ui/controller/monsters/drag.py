"""拖动排序：按住、每帧跟着光标算落点、松手落库。"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot
from PySide6.QtGui import QGuiApplication

from ...toolkit.desktop import _cursor_down, _cursor_pos

class DragMixin:
    @Slot(result="QVariantList")
    def cursorState(self) -> list:
        """`[x, y, down]`：光标在**逻辑像素**下的位置、左键还按着没有。

        给"编辑模式抓一格拖到「这一层」某一行上"用：跨窗口的真拖放（QDrag）会进模态
        循环，无头环境和某些机器上根本拖不动，所以那一处改成**QML 定时轮询光标**。

        **必须除掉 devicePixelRatio**：`_cursor_pos()` 给的是物理像素，而 QML 那边
        比的是窗口/场景坐标（逻辑像素）。150% 缩放下差 1.5 倍，行永远命中不了 ——
        拖到行上松手却"什么都没记"就是这么来的（用户 2026-10-31 "还是没法拖动"）。
        读不到光标就当没按着（一次失败不能把拖拽卡住）。
        """
        try:
            x, y = _cursor_pos()
        except Exception:
            return [0, 0, False]
        try:
            down = bool(_cursor_down())
        except Exception:
            down = False
        try:
            screen = QGuiApplication.primaryScreen()
            scale = float(screen.devicePixelRatio()) if screen else 1.0
        except Exception:
            scale = 1.0
        if scale <= 0:
            scale = 1.0
        return [int(round(x / scale)), int(round(y / scale)), down]

    @Slot(int, float, float, int)
    def monDragStart(self, index, top_y, row_height, count) -> None:
        """开始拖某一行。

        index 是按下时那一行；top_y 是**第一行顶部在屏幕上的 y**（逻辑像素，
        已经扣掉滚动距离）；row_height 行高；count 行数。
        """
        from .... import trace
        if count <= 0:
            return
        self._mon_drag = {"from": int(index), "to": int(index),
                          "top": float(top_y),
                          "row": max(8.0, float(row_height)),
                          "count": int(count)}
        self._mon_drag_timer.start()
        self.monDragChanged.emit()
        trace.note("manual.mon_drag_start", index=int(index))

    @Slot()
    def monDragFinish(self) -> None:
        drag = self._mon_drag
        self._mon_drag = None
        self._mon_drag_timer.stop()
        self.monDragChanged.emit()
        if not drag:
            return
        from_index = drag["from"]
        to_index = drag["to"]
        if from_index < 0 or to_index < 0 or from_index == to_index:
            return
        self.moveMonster(from_index, to_index)

    def _tick_mon_drag(self) -> None:
        drag = self._mon_drag
        if not drag:
            self._mon_drag_timer.stop()
            return
        try:
            _x, y = _cursor_pos()
            screen = QGuiApplication.primaryScreen()
            dpr = screen.devicePixelRatio() if screen else 1.0
            y = float(y) / float(dpr or 1.0)   # 光标是物理像素，窗口坐标是逻辑像素
        except Exception:
            self.monDragFinish()
            return
        index = int((y - drag["top"]) // drag["row"])
        index = max(0, min(drag["count"] - 1, index))
        if index != drag["to"]:
            drag["to"] = index
            self.monDragChanged.emit()
        # 鼠标已经松开（松开事件可能没送到那一行）→ 就地下单
        try:
            if not _cursor_down():
                self.monDragFinish()
        except Exception:
            pass

    # ---- 怪物拖拽排序：按刷新率读光标算落点 ----
    # 为什么不用 QML 的鼠标事件：指针一离开那一行，Qt 就给 MouseArea 发 canceled，
    # 抓取式的拖拽会断在半路（实测）。这里和窗口拖动一样，直接读系统光标。

    def _get_mon_drag_from(self):
        return self._mon_drag["from"] if self._mon_drag else -1

    def _get_mon_drag_to(self):
        return self._mon_drag["to"] if self._mon_drag else -1
