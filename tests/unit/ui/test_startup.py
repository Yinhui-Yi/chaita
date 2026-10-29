"""启动/收尾单元测试（`chaita/ui/startup.py`）。

真值来自规则：单实例锁防叠开、软件渲染逃生口、崩溃日志真的开了 faulthandler。
"""

import os

import chaita.ui.startup as su


def test_render_backend_hint_software(monkeypatch):
    monkeypatch.setenv("CHAITA_RENDER", "software")
    monkeypatch.delenv("QT_QUICK_BACKEND", raising=False)
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    su._render_backend_hint()
    assert os.environ["QT_QUICK_BACKEND"] == "software"


def test_render_backend_hint_auto_leaves_default(monkeypatch):
    monkeypatch.setenv("CHAITA_RENDER", "")
    monkeypatch.delenv("QT_QUICK_BACKEND", raising=False)
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)
    su._render_backend_hint()
    assert "QT_QUICK_BACKEND" not in os.environ


def test_single_instance_skip_env(monkeypatch):
    monkeypatch.setenv("CHAITA_SKIP_SINGLE_INSTANCE", "1")
    assert su._single_instance() is True


def test_single_instance_acquires_lock(monkeypatch):
    monkeypatch.delenv("CHAITA_SKIP_SINGLE_INSTANCE", raising=False)

    class Lock:
        def setStaleLockTime(self, t):
            pass

        def tryLock(self, t):
            return True

    monkeypatch.setattr(su, "QLockFile", lambda path: Lock())
    assert su._single_instance() is True
    assert su._SINGLE_LOCK is not None


def test_single_instance_already_running(monkeypatch):
    monkeypatch.delenv("CHAITA_SKIP_SINGLE_INSTANCE", raising=False)

    class Lock:
        def setStaleLockTime(self, t):
            pass

        def tryLock(self, t):
            return False

        def getLockInfo(self):
            return (4321, "ADMIN", "python")

    monkeypatch.setattr(su, "QLockFile", lambda path: Lock())
    monkeypatch.setattr(su, "focus_window_of_process", lambda pid: False)
    assert su._single_instance() is False


def test_already_running_raises_the_window_of_the_lock_owner(monkeypatch):
    """第二次启动不能只是"这次不开"：要把锁的主人那扇窗叫到前面。

    用户点图标看不到任何反应 = 打不开（用户："我怎么打不开软件了"），
    所以失败这条路必须拿锁里记的 PID 去找窗口。
    """
    monkeypatch.delenv("CHAITA_SKIP_SINGLE_INSTANCE", raising=False)
    asked = []

    class Lock:
        def setStaleLockTime(self, t):
            pass

        def tryLock(self, t):
            return False

        def getLockInfo(self):
            return (4321, "ADMIN", "python")

    monkeypatch.setattr(su, "QLockFile", lambda path: Lock())
    monkeypatch.setattr(su, "focus_window_of_process",
                        lambda pid: asked.append(pid) or True)
    assert su._single_instance() is False
    assert asked == [4321]


def test_already_running_without_lock_info_guesses_no_window(monkeypatch):
    """锁里读不出 PID 就别乱猜窗口（猜错会把别人的窗口顶上来）。"""
    monkeypatch.delenv("CHAITA_SKIP_SINGLE_INSTANCE", raising=False)
    asked = []

    class Lock:
        def setStaleLockTime(self, t):
            pass

        def tryLock(self, t):
            return False

        def getLockInfo(self):
            return None

    monkeypatch.setattr(su, "QLockFile", lambda path: Lock())
    monkeypatch.setattr(su, "focus_window_of_process",
                        lambda pid: asked.append(pid) or False)
    assert su._single_instance() is False
    assert asked == [0]


def test_release_single_instance_unlocks():
    class Lock:
        def __init__(self):
            self.unlocked = False

        def unlock(self):
            self.unlocked = True

    lock = Lock()
    su._SINGLE_LOCK = lock
    su._release_single_instance()
    assert lock.unlocked is True
    assert su._SINGLE_LOCK is None


def test_enable_crash_log_enables_faulthandler(monkeypatch):
    import faulthandler
    calls = []

    def fake_enable(file=None, all_threads=False):
        calls.append((file, all_threads))

    monkeypatch.setattr(faulthandler, "enable", fake_enable)
    monkeypatch.setattr("builtins.open", lambda *a, **k: "handle")
    su._enable_crash_log()
    assert calls == [("handle", True)]


# ---- 边角：出错也不能把启动/收尾带崩 ----

def test_release_single_instance_swallows_unlock_error():
    class Lock:
        def unlock(self):
            raise RuntimeError("锁文件被别人删了")

    su._SINGLE_LOCK = Lock()
    su._release_single_instance()          # 不抛
    assert su._SINGLE_LOCK is None


def test_enable_crash_log_swallows_open_error(monkeypatch):
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("没权限")))
    monkeypatch.delattr(su._enable_crash_log, "handle", raising=False)

    su._enable_crash_log()                 # 不抛（日志写不了也得能开软件）

    # 打不开就别留半个 handle，下次还能重试
    assert getattr(su._enable_crash_log, "handle", None) is None


def test_render_backend_hint_swallows_trace_error(monkeypatch):
    monkeypatch.setenv("CHAITA_RENDER", "")
    monkeypatch.delenv("QT_QUICK_BACKEND", raising=False)
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))

    su._render_backend_hint()              # 不抛

    assert "QT_QUICK_BACKEND" not in os.environ   # 也没乱改渲染后端


def test_main_returns_zero_when_already_running(monkeypatch):
    monkeypatch.setattr(su, "_enable_crash_log", lambda: None)
    monkeypatch.setattr(su, "_render_backend_hint", lambda: None)
    monkeypatch.setattr(su, "_single_instance", lambda: False)
    released = []
    monkeypatch.setattr(su, "_release_single_instance",
                        lambda: released.append(1))
    monkeypatch.setattr(su, "_run",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("已经开着了不该再跑一次")))

    assert su.main() == 0
    # 已经开着了就直接 return，锁本来就不是我们的，没什么可放
    assert released == []


def test_main_returns_run_code_and_releases(monkeypatch):
    monkeypatch.setattr(su, "_enable_crash_log", lambda: None)
    monkeypatch.setattr(su, "_render_backend_hint", lambda: None)
    monkeypatch.setattr(su, "_single_instance", lambda: True)
    released = []
    monkeypatch.setattr(su, "_release_single_instance",
                        lambda: released.append(1))
    monkeypatch.setattr(su, "_run", lambda: 3)

    assert su.main() == 3
    assert released == [1]


# ---- _run：启动顺序（窗口属性、贴边、命中测试、收尾）----

class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)


class _Ctx:
    def __init__(self):
        self.props = {}

    def setContextProperty(self, key, value):
        self.props[key] = value


class _Win:
    def __init__(self):
        self.props = {}
        self.visible = None
        self.deleted = False

    def setProperty(self, key, value):
        self.props[key] = value

    def property(self, key):
        return self.props.get(key)

    def setVisible(self, value):
        self.visible = value

    def deleteLater(self):
        self.deleted = True


class _Engine:
    def __init__(self, roots=None):
        self.roots = [ _Win() ] if roots is None else roots
        self.ctx = _Ctx()
        self.deleted = False

    def rootContext(self):
        return self.ctx

    def rootObjects(self):
        return self.roots

    def deleteLater(self):
        self.deleted = True


class _App:
    def __init__(self, argv):
        self.argv = argv
        self.name = ""
        self.aboutToQuit = _Signal()
        self.filters = []
        self.code = 7

    def setApplicationName(self, name):
        self.name = name

    def installNativeEventFilter(self, f):
        self.filters.append(f)

    def exec(self):
        return self.code

    @staticmethod
    def instance():
        return None


class _Controller:
    def __init__(self):
        self.window = None
        self.ready = False
        self.shutdown = False

    def attach(self, window):
        self.window = window

    def _begin_shutdown(self):
        self.shutdown = True

    def markGeometryReady(self):
        self.ready = True

    def deleteLater(self):
        pass


def _fake_run(monkeypatch, applied=True, roots=None):
    """把 `_run` 的每个边界都换掉，只留下**顺序**是真的。"""
    calls = {}
    engine = _Engine(roots=roots)
    controller = _Controller()
    app = _App(["prog"])

    monkeypatch.setattr(su, "QGuiApplication", lambda argv: app)
    monkeypatch.setattr(su, "QQmlApplicationEngine", lambda: engine)
    monkeypatch.setattr(su, "Controller", lambda: controller)
    monkeypatch.setattr(su, "load_into", lambda e: calls.setdefault("loaded", e))
    monkeypatch.setattr(su, "_apply_ui_state",
                        lambda w: (calls.setdefault("applied", w), applied)[1])
    monkeypatch.setattr(su, "_place_right",
                        lambda w: calls.setdefault("placed", w))
    monkeypatch.setattr(su, "NativeHitTest", lambda w: ("hit", w))
    monkeypatch.setattr(su, "_teardown",
                        lambda a, e, w, c: calls.setdefault(
                            "torn", (a, e, w, c)))
    return calls, app, engine, controller


def test_run_wires_the_window_in_order(monkeypatch):
    calls, app, engine, controller = _fake_run(monkeypatch, applied=False)
    window = engine.roots[0]

    assert su._run() == 7                  # exec() 的返回码原样传出去

    assert app.name == "ChaitaAssistant"
    assert app.aboutToQuit.slots == [controller._begin_shutdown]
    assert engine.ctx.props["controller"] is controller
    assert controller.window is window
    assert window.props["appTitle"] == su.APP_TITLE
    assert window.props["heroIcon"] == su.HERO_ICON
    assert window.props["iconBase"] == su.ICON_BASE
    assert window.props["itemBase"] == su.ITEM_BASE
    assert window.props["collapsed"] is False
    assert window.props["entered"] is True
    assert controller.ready is True
    assert calls["placed"] is window       # 没有存档才贴右边
    assert app.filters == [("hit", window)]
    assert calls["torn"] == (app, engine, window, controller)


def test_run_keeps_saved_position_when_state_exists(monkeypatch):
    calls, app, engine, controller = _fake_run(monkeypatch, applied=True)
    su._run()
    assert "applied" in calls
    assert "placed" not in calls           # 有存档就别贴右边


def test_run_returns_one_when_qml_fails(monkeypatch):
    calls, app, engine, controller = _fake_run(monkeypatch, roots=[])
    assert su._run() == 1
    assert "torn" not in calls             # 窗口都没建出来，没什么可拆的
