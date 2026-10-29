"""窗口这一摊：尺寸/折叠动画、拖动、贴边、退出、前台采样。

为什么插值在 Python：QML 侧改 `Window.height` 时 Behavior 和 NumberAnimation 都不生效
（实测直接跳变），只能逐帧改。拖动同理：按刷新率节流，别让一次移动发几十个事件。
"""

import time

from PySide6.QtCore import Slot
from PySide6.QtGui import QGuiApplication

from ..constants import DRAG_INTERVAL_MS
from ..toolkit.state import (_apply_ui_state, _geometry_from_state,
                             _load_ui_state, _place_right, _save_session,
                             _save_ui_state)


class WindowMixin:
    def _sample_foreground(self) -> None:
        if self._closing:
            return
        try:
            from ...game import winutil
        except Exception:
            # 非 Windows（比如容器里跑界面测试）没有 win32api，直接跳过采样
            return

        hwnd = winutil.foreground_top_window()
        if hwnd is None:
            return
        process = winutil.process_name(hwnd)
        if not process:
            return
        # 悬浮层自己不算，否则点按钮时会把记录覆盖成 pythonw.exe
        if process.startswith("python"):
            return
        self._last_foreground = process
        # 记住"刚才在看的那扇窗"：点我们自己的按钮后前台就变成悬浮层了，
        # 抓图只能靠这个判断该抓哪个浏览器窗口（两个页面 = 两个窗口、同一个进程）
        winutil.remember_foreground(hwnd)

    # ---- 供 QML 读取的属性 ----
    @Slot(int, int, int)
    def animateSize(self, to_w: int, to_h: int, duration_ms: int) -> None:
        """把窗口尺寸动画到目标值。"""
        if self._win is None:
            return
        self._anim_from = (int(self._win.property("width")),
                           int(self._win.property("height")))
        self._anim_to = (int(to_w), int(to_h))
        self._anim_ms = max(1, int(duration_ms))
        self._anim_start = time.monotonic()
        self._anim.start()

    def _tick_size(self) -> None:
        if self._win is None:
            self._anim.stop()
            return
        progress = (time.monotonic() - self._anim_start) / (self._anim_ms / 1000.0)
        if progress >= 1.0:
            progress = 1.0
        # OutCubic
        eased = 1.0 - (1.0 - progress) ** 3
        w = round(self._anim_from[0] + (self._anim_to[0] - self._anim_from[0]) * eased)
        h = round(self._anim_from[1] + (self._anim_to[1] - self._anim_from[1]) * eased)
        self._win.setProperty("width", int(w))
        self._win.setProperty("height", int(h))
        if progress >= 1.0:
            self._anim.stop()
            self.sizeAnimDone.emit()

    def attach(self, window) -> None:
        """绑定 QML 根窗口。必须在 loadData 之后调用。"""
        self._win = window

    # ---- 窗口位置/大小：记下来，下次启动照原样 ----
    @Slot()
    def markGeometryReady(self) -> None:
        """启动摆位完成后调一次：之前的坐标都是窗口创建时的 0,0，不能记。"""
        self._geometry_ready = True

    @Slot(int, int, int, int)
    def rememberWindow(self, x, y, width, height) -> None:
        """QML 那边窗口一动就报一次；宽度/高度给 0 表示"位置变了、尺寸别覆盖"。"""
        if not self._geometry_ready:
            return
        geometry = {"x": int(x), "y": int(y)}
        if int(width) > 0 and int(height) > 0:
            geometry["width"] = int(width)
            geometry["height"] = int(height)
        self._pending_geometry = geometry
        self._state_timer.start()

    def _flush_ui_state(self) -> None:
        geometry = self._pending_geometry
        if not geometry:
            return
        self._pending_geometry = None
        data = _load_ui_state()
        data.update(geometry)
        _save_ui_state(data)

    @Slot()
    def _begin_shutdown(self) -> None:
        """收尾：停掉所有定时器、置关闭标志、等后台线程收工。

        为什么要有它：后台线程（读图/数怪/对话）会通过 `uiCall` 信号回到界面线程，
        如果这时窗口/Controller 已经开始销毁，就是往已释放的对象上发信号 ——
        实测出现过 "Python.exe 应用程序错误：该内存不能为 read" 的闪退。
        """
        if getattr(self, "_closing", False):
            return
        self._closing = True
        for timer in (self._poll, self._timer, self._state_timer,
                      self._mon_drag_timer):
            try:
                timer.stop()
            except Exception:
                pass
        # 最多等 2 秒：读取任务本身可能要几十秒，不能陪它等到天亮
        deadline = time.time() + 2.0
        for thread in list(getattr(self, "_threads", [])):
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                thread.join(timeout=remaining)
            except Exception:
                break

    @Slot()
    def quit(self) -> None:
        """退出程序。

        **必须带 @Slot()**：QML 那边是 `win.requestQuit()` → `controller.quit()`，
        没有这个装饰器时 PySide 不把它注册进 metaobject，QML 会报
        `TypeError: Property 'quit' of object Controller(...) is not a function`，
        点了右上角 ✕ / 按 Esc 都**一点反应都没有**（用户："我怎么关不掉了"）。
        `tools/check_close.py a` 就是量这一下的。
        """
        _save_session(self._monsters, self._map_history)
        self._begin_shutdown()
        app = QGuiApplication.instance()
        if app is not None:
            app.quit()

    @Slot(int, int)
    def dragStart(self, offset_x: int, offset_y: int) -> None:
        """offset 是按下时鼠标在窗口内的逻辑坐标。"""
        if self._win is None:
            return
        self._drag_offset = (offset_x, offset_y)
        self._last_pos = None
        self._drag_active = True
        self._timer.start()

    @Slot()
    def dragEnd(self) -> None:
        self._drag_active = False
        self._timer.stop()
        if self._win is not None:
            self._win.setProperty("x", int(self._win.property("x")))
            self._win.setProperty("y", int(self._win.property("y")))

    def _tick_drag(self) -> None:
        if not self._drag_active or self._win is None:
            return
        import win32api

        cx, cy = win32api.GetCursorPos()
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        # 光标是物理像素，窗口坐标是逻辑像素
        x = int(cx / dpr - self._drag_offset[0])
        y = int(cy / dpr - self._drag_offset[1])
        if (x, y) == self._last_pos:
            return
        self._last_pos = (x, y)
        self._win.setProperty("x", x)
        self._win.setProperty("y", y)
