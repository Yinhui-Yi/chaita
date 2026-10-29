"""和 Windows 桌面打交道：光标位置、按键状态、边缘命中测试、把别的实例叫到前面。"""

import ctypes
from ctypes import wintypes

from .. import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import QAbstractNativeEventFilter

from ..constants import APP_TITLE, _BORDER, _HTBOTTOM, _HTBOTTOMLEFT, _HTBOTTOMRIGHT, _HTLEFT, _HTRIGHT, _HTTOP, _HTTOPLEFT, _HTTOPRIGHT

# ShowWindow / SetWindowPos 的参数（只用到这几个）
_SW_RESTORE = 9
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2
_SWP_NOMOVE_NOSIZE = 0x0001 | 0x0002


def _top_windows_of(pid: int) -> list:
    """这个进程的（标题, 句柄）列表：只要可见、有标题的顶层窗口。

    隐藏的窗口不算（用户看不见，叫到前面也没用），没标题的也不算（那是
    Qt 的内部窗口）。返回顺序就是 EnumWindows 的 z 序（上层在前）。
    """
    user32 = ctypes.windll.user32
    found = []

    def visit(hwnd, _param):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        found.append((buf.value, hwnd))
        return True

    user32.EnumWindows(
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return found


def _main_window_of(pid: int) -> int:
    """这个进程的主面板句柄（0 = 没有）。

    一个进程可能同时开着「这一层」/伤害计算那些小窗，它们的标题是层名；
    优先认主面板（`APP_TITLE`），没有就退回最上面那扇。
    """
    windows = _top_windows_of(pid)
    for title, hwnd in windows:
        if title == APP_TITLE:
            return hwnd
    return windows[0][1] if windows else 0


def focus_window_of_process(pid: int) -> bool:
    """把已经在跑的那个实例的窗口提到最前（返回 False = 没找到窗口）。

    第二次点图标时用。单实例只是"这次不开"，可用户的窗口还压在别的窗口后面，
    界面上等于什么都没发生（用户："我怎么打不开软件了"），所以这条路必须
    真的把已有窗口叫出来。

    抢前台会被 Windows 拒绝（后台进程没有前台权限），所以先置顶再取消置顶：
    这一下能把窗口真的升到最前，再要焦点才有效（实测前台真的切过去了）。
    """
    if pid <= 0:
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = _main_window_of(pid)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0, _SWP_NOMOVE_NOSIZE)
        user32.SetWindowPos(hwnd, _HWND_NOTOPMOST, 0, 0, 0, 0, _SWP_NOMOVE_NOSIZE)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False



def _cursor_pos():
    """当前光标位置（物理像素）。测试里会把它换掉。"""
    import win32api
    return win32api.GetCursorPos()

def _cursor_down():
    """鼠标左键是不是还按着。松开事件可能送不到那一行，所以靠这个兜底。"""
    import win32api
    return bool(win32api.GetAsyncKeyState(0x01) & 0x8000)

class NativeHitTest(QAbstractNativeEventFilter):
    """把窗口边缘的命中测试交回给 Windows。

    必须用 QAbstractNativeEventFilter 装在 QGuiApplication 上：装在窗口自己身上
    的 installEventFilter 收不到 NativeEvent（实测 0 次），这条路走不通。

    只管**主窗口**。「这一层」的小窗是 QML 里动态开的真窗口，它的宽高是绑定出来的，
    交给系统改尺寸会和绑定打架（实测窗口被顶成 13×280）—— 那一扇走 QML 自己的
    四边把手，见 MainWindow.qml 的 SheetGrip。
    """

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._hwnd = int(window.winId())
        self._make_resizable()

    def _make_resizable(self) -> None:
        """给无边框窗口补上 WS_THICKFRAME。

        光在 WM_NCHITTEST 里返回 HTLEFT/HTBOTTOM 是不够的：没有 WS_THICKFRAME 时
        DefWindowProc 不会进入"拖边缘改尺寸"的循环，表现为"边缘能命中但拖不动"
        （用户："怎么不能修改窗口大小"）。
        """
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            gwl_style = -16
            ws_thickframe = 0x00040000
            style = user32.GetWindowLongW(self._hwnd, gwl_style) & 0xFFFFFFFF
            if style & ws_thickframe:
                return
            user32.SetWindowLongW(self._hwnd, gwl_style, style | ws_thickframe)
            # 改完样式要让窗口重新算一次非客户区
            user32.SetWindowPos(self._hwnd, 0, 0, 0, 0, 0,
                                0x0002 | 0x0004 | 0x0100 | 0x0020)
        except Exception:
            # 拿不到窗口样式不影响别的功能：边缘命中测试还照旧
            pass

    def nativeEventFilter(self, event_type, message):
        try:
            return self._handle(message)
        except Exception:
            # 这里以前吞掉过一个真正的 bug：`ctypes.wintypes` 没导入，
            # _handle 每次都抛 AttributeError，边缘命中测试整条路静默失效
            # （用户："怎么不能修改窗口大小"）。所以失败要能看见，但只记第一次，
            # 不然鼠标一动就刷一屏日志。
            if not getattr(self, "_reported_failure", False):
                self._reported_failure = True
                try:
                    from ... import trace
                    import traceback
                    trace.note("hit_test.failed",
                               error=traceback.format_exc(limit=2)[-300:])
                except Exception:
                    pass
            return False, 0

    def _handle(self, message):
        ptr = int(message)
        if not ptr:
            return False, 0

        msg = wintypes.MSG.from_address(ptr)
        if msg.message != 0x0084:  # WM_NCHITTEST
            return False, 0
        if int(msg.hWnd) != self._hwnd:
            return False, 0

        screen = self._window.screen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        x = ctypes.c_short(msg.lParam & 0xFFFF).value
        y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value

        geometry = self._window.geometry()
        left = geometry.x() * dpr
        top = geometry.y() * dpr
        right = (geometry.x() + geometry.width()) * dpr
        bottom = (geometry.y() + geometry.height()) * dpr
        border = max(5, int(_BORDER * dpr))

        on_left = x < left + border
        on_right = x >= right - border
        on_top = y < top + border
        on_bottom = y >= bottom - border

        if on_top and on_left:
            return True, _HTTOPLEFT
        if on_top and on_right:
            return True, _HTTOPRIGHT
        if on_bottom and on_left:
            return True, _HTBOTTOMLEFT
        if on_bottom and on_right:
            return True, _HTBOTTOMRIGHT
        if on_left:
            return True, _HTLEFT
        if on_right:
            return True, _HTRIGHT
        if on_top:
            return True, _HTTOP
        if on_bottom:
            return True, _HTBOTTOM

        # 顶栏不报 HTCAPTION。报的话 Windows 会接管整个顶栏的鼠标事件，
        # QML 里的「关闭」按钮和「折叠」点击就再也收不到了 —— 实测两者会一起失效。
        # 顶栏拖动因此交回 QML（Controller.dragStart/dragEnd）。
        return False, 0
