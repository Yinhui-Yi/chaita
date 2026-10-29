"""启动与收尾：崩溃日志、渲染后端、main()、按顺序拆窗口。"""

import os
import sys

from . import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import QCoreApplication, QEvent, QLockFile, QUrl, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .constants import APP_TITLE, HERO_ICON, ICON_BASE, ITEM_BASE, _LOGS
from .controller.controller import Controller
from .toolkit.desktop import NativeHitTest, focus_window_of_process
from .toolkit.state import _apply_ui_state, _place_right
from .loader import load_into

# 单实例锁：留着引用，进程活多久锁就占多久
_SINGLE_LOCK = None


def _raise_running_instance(lock) -> bool:
    """锁被别的实例拿着：把它那扇窗叫到最前（返回 False = 没叫出来）。

    只往 stderr 打一行是不够的：`启动.vbs` 用的是 pythonw，根本没有控制台，
    用户看到的就是"图标点了没反应"（用户："我怎么打不开软件了"）。
    """
    pid = 0
    try:
        info = lock.getLockInfo()       # (pid, hostname, appname)
        pid = int(info[0]) if info else 0
    except Exception:
        pid = 0
    raised = focus_window_of_process(pid)
    try:
        from .. import trace
        trace.note("app.already_running", pid=pid, raised=raised)
    except Exception:
        pass
    return raised


def _single_instance() -> bool:
    """返回 False = 已经有一个在跑，这次别开第二个悬浮层（顺手把那个叫到前面）。

    为什么要有：连点两次启动器/图标会叠出**两个**悬浮层（实测：两个进程、两个
    `QaitAssistant` 窗口），两个都盖在游戏上、都去抓图，用户根本分不清点哪个。

    用 `QLockFile`（`logs/app.lock`）：锁里记着 PID，进程崩了留下的死锁会被
    下一次启动认出来并接管（`staleLockTime = 0` 就是"只看进程在不在"）。
    """
    global _SINGLE_LOCK
    # 自检工具（tools/smoke_close.py 等）要能在"用户正开着一个"的情况下跑一次：
    # 只认这个显式开关，正常启动不受影响。
    if os.environ.get("CHAITA_SKIP_SINGLE_INSTANCE") == "1":
        return True
    lock = QLockFile(os.path.join(_LOGS, "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        _raise_running_instance(lock)
        return False
    _SINGLE_LOCK = lock
    return True


def _release_single_instance() -> None:
    global _SINGLE_LOCK
    if _SINGLE_LOCK is not None:
        try:
            _SINGLE_LOCK.unlock()
        except Exception:
            pass
        _SINGLE_LOCK = None


def _enable_crash_log() -> None:
    """把 Python 级/原生级崩溃都写进 logs/crash.log（下次闪退能查到现场）。

    faulthandler 对 0xC0000005（访问违例）也会输出 "Windows fatal exception" +
    各线程的 Python 栈，比 Windows 那个"内存不能为 read"的弹窗有用得多。
    """
    try:
        import faulthandler
        path = os.path.join(_LOGS, "crash.log")
        handle = open(path, "a", buffering=1, encoding="utf-8")
        faulthandler.enable(file=handle, all_threads=True)
        _enable_crash_log.handle = handle     # 别让 handle 被回收掉
    except Exception:
        pass

def _render_backend_hint() -> None:
    """记录/可切换渲染后端。

    这台机器上出现过 GPU 层的 LiveKernelEvent（显示驱动看门狗）和
    "该内存不能为 read" 的闪退，所以留一个逃生口：
        set CHAITA_RENDER=software
    就走 Qt 的软件渲染（像素画界面完全够用，能绕开显卡驱动那一层）。
    """
    choice = (os.environ.get("CHAITA_RENDER") or "").strip().lower()
    if choice in ("software", "soft", "cpu"):
        os.environ["QT_QUICK_BACKEND"] = "software"
        os.environ.setdefault("QT_OPENGL", "software")
    try:
        from .. import trace
        trace.note("app.start", qt_version=str(qVersion()),
                   render=(choice or "auto"))
    except Exception:
        pass

def main() -> int:
    _enable_crash_log()
    _render_backend_hint()
    # 已经开着一个就直接退：再开一个会叠出第二个悬浮层（两个都盖在游戏上）
    if not _single_instance():
        print("拆塔辅助已经开着了，这次不重复打开", file=sys.stderr)
        return 0
    try:
        return _run()
    finally:
        _release_single_instance()


def _run() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("ChaitaAssistant")

    # 必须留引用：否则 Controller 会被 GC，QML 拿到空壳，点关闭没反应
    controller = Controller()
    # 关窗口（点 × / Alt+F4）也要走同一套收尾：停定时器、等后台线程
    app.aboutToQuit.connect(controller._begin_shutdown)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    load_into(engine)

    if not engine.rootObjects():
        print("悬浮层加载失败", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    controller.attach(window)
    window.setProperty("appTitle", APP_TITLE)
    window.setProperty("heroIcon", HERO_ICON)
    window.setProperty("iconBase", ICON_BASE)
    window.setProperty("itemBase", ITEM_BASE)
    # 上次拖到哪、拉多大就还摆哪；没有记录（第一次开/记录坏了）才贴右边。
    # 必须在"展开"之前调用：展开动画的目标尺寸来自 savedWidth/savedHeight。
    if not _apply_ui_state(window):
        _place_right(window)
    # 第一次打开就是展开态，让用户看到全貌；之后再折叠才记住折叠状态
    window.setProperty("collapsed", False)
    controller.markGeometryReady()
    # 窗口即将第一次显示：这时再让 QML 播入场动画。
    # （在 loadData 时就播会赶在窗口出现之前跑完，等于没有。）
    window.setProperty("entered", True)

    # 把边缘缩放与光标反馈交回给 Windows。必须装在 app 上（窗口级过滤器收不到
    # NativeEvent），且必须留引用，否则被 GC 后静默失效。
    hit_test = NativeHitTest(window)
    app.installNativeEventFilter(hit_test)

    code = app.exec()
    _teardown(app, engine, window, controller)
    return code

def _teardown(app, engine, window, controller) -> None:
    """按顺序拆：先停线程/定时器 → 关窗口 → **真的销毁 QML** → 再断开 controller。

    为什么讲究顺序：以前 QML 还活着、controller 就已经变成 null，收尾时刷一屏
    "Cannot read property 'x' of null"；更糟的是这种"拆到一半还在求值"最容易
    触发底层的访问违例（用户看到的 "内存不能为 read" 闪退）。
    """
    from PySide6.QtCore import QCoreApplication, QEvent

    def flush_deletes() -> None:
        # deleteLater 排的是 DeferredDelete 事件，processEvents 不会处理它，
        # 必须显式 sendPostedEvents 才会当场销毁
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QCoreApplication.processEvents()

    try:
        controller._begin_shutdown()
    except Exception:
        pass
    try:
        window.setVisible(False)
        QCoreApplication.processEvents()
    except Exception:
        pass
    try:
        window.deleteLater()
        flush_deletes()          # QML 树这会儿真的没了，后面就没人再去读 controller
    except Exception:
        pass
    try:
        engine.rootContext().setContextProperty("controller", None)
    except Exception:
        pass
    try:
        engine.deleteLater()
        flush_deletes()
    except Exception:
        pass
    try:
        controller.deleteLater()
        flush_deletes()
    except Exception:
        pass
