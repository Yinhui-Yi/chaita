"""关窗口这条路径到底怎么了 —— 一次只测一件事（窗口放屏幕外，不碰桌面）。

用户报"我怎么关不掉了"。先复现，别猜。

    tools\\check_close.py a   # 点右上角 ✕：真的会退出吗？多久？点了之后窗口有没有反应？
    tools\\check_close.py b   # 点地图块打开大图，再点一下能不能关掉（不能顺手把程序关了）
    tools\\check_close.py c   # 光标在输入框里时按 Esc 不退；挪开焦点再按一次才退

每条都是独立进程：真让程序退出，退出前后各打一行，用来量"从点击到窗口消失"的延迟。
"""

import os
import sys
# 中文控制台是 GBK：检查项名里带 ✕ 会抛 UnicodeEncodeError，把检查打断
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PySide6.QtCore import QTimer, QUrl, Qt, QPoint  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402,F401
from PySide6.QtTest import QTest  # noqa: E402

from chaita.ui import main as ov  # noqa: E402

CASE = (sys.argv[1] if len(sys.argv) > 1 else "a").lower()
STATE = {"click_at": None, "quit_at": None, "visible_at_click": None}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)


def quiet_crash_dialogs():
    try:
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    except Exception:
        pass


def hosts(window):
    """主窗口 + 它开出来的真窗口（「这一层」/ 伤害计算）。"""
    out = [window]
    try:
        names = window.property("floorWindows")
        names = names.toVariant() if hasattr(names, "toVariant") else names
        for name in names or []:
            sheet = window.floorSheetOf(str(name))
            if sheet is not None:
                out.append(sheet)
        battle = window.property("battleWindow")
        if hasattr(battle, "toQObject"):
            battle = battle.toQObject()
        if battle is not None:
            out.append(battle)
    except (RuntimeError, AttributeError):
        pass
    return out


def walk(window):
    out = []
    for host in hosts(window):
        stack = list(host.contentItem().childItems())
        while stack:
            node = stack.pop()
            out.append(node)
            stack.extend(node.childItems())
    return out


def host_of(window, item):
    node = item
    while node is not None:
        for host in hosts(window):
            if node is host.contentItem():
                return host
        node = node.parentItem()
    return window


def click(window, item):
    host = host_of(window, item)
    point = centre_in_window(host, item)
    QTest.mouseClick(host, Qt.LeftButton, Qt.NoModifier, point)
    QGuiApplication.instance().processEvents()


def shown(item):
    node = item
    while node is not None:
        if not node.isVisible():
            return False
        node = node.parentItem()
    return True


def by_object(window, name):
    return [i for i in walk(window) if i.objectName() == name and shown(i)]


def centre_in_window(window, item):
    point = item.mapToScene(QPoint(int(item.width() / 2),
                                   int(item.height() / 2)))
    return QPoint(int(point.x()), int(point.y()))


def _thumb():
    """一张真实的缩略图（点地图块能不能开大图，得真有图才测得出来）。"""
    sample = os.path.join(ROOT, "docs", "capture", "h5_miaomiao_212609.png")
    if not os.path.exists(sample):
        return ""
    import cv2
    import numpy as np
    image = cv2.imdecode(np.fromfile(sample, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return ""
    return ov._save_thumb(image, "check_close_thumb", width=200)


def build():
    controller = ov.Controller()
    controller._map_history = [
        {"floor": "地下30", "url": _thumb(),
         "mons": [{"name": "红头怪", "count": 2}],
         "items": [{"name": "红血瓶", "effect": "300", "count": 1,
                    "icon": "potion_red"}]},
    ]
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    ov.load_into(engine)
    if not engine.rootObjects():
        raise SystemExit("QML 没加载起来")
    window = engine.rootObjects()[0]
    controller.attach(window)
    window.setProperty("appTitle", ov.APP_TITLE)
    window.setProperty("heroIcon", ov.HERO_ICON)
    window.setProperty("iconBase", ov.ICON_BASE)
    window.setProperty("itemBase", ov.ITEM_BASE)
    window.setProperty("collapsed", False)
    window.setProperty("x", -6000)
    window.setProperty("y", -6000)
    controller.statusTextChanged.emit()
    controller.mapHistoryChanged.emit()
    controller.monstersChanged.emit()
    window.show()
    return controller, engine, window


# ------------------------------------------------------------------ 三个场景
def case_a(window):
    """点右上角 ✕。"""
    buttons = by_object(window, "closeBtn")
    check("找到右上角的关闭按钮", len(buttons) >= 1, "count=%d" % len(buttons))
    if not buttons:
        finish()
        return

    def press():
        point = centre_in_window(window, buttons[0])
        STATE["click_at"] = time.time()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        QTimer.singleShot(200, after_click)

    def after_click():
        # 点了以后窗口马上有没有反应（藏起来 / 变暗都算），用户等的是这个
        STATE["visible_at_click"] = bool(window.isVisible())
        QTimer.singleShot(6000, give_up)

    def give_up():
        check("点 ✕ 之后 6 秒内窗口消失", False,
              "6 秒还没退出（窗口还开着）")
        finish()

    QTimer.singleShot(600, press)


def case_b(window):
    """点地图块打开这一层 → 点截图看大图 → 点一下关大图 → 关掉这一层。"""
    def open_sheet():
        tiles = by_object(window, "mapTile")
        check("找得到地图块", len(tiles) >= 1, "count=%d" % len(tiles))
        if not tiles:
            finish()
            return
        click(window, tiles[0])
        QTimer.singleShot(400, after_sheet)

    def after_sheet():
        check("点地图块打开这一层的子界面",
              window.property("openFloor") not in ("", None)
              and bool(by_object(window, "floorCard")),
              "openFloor=%r" % (window.property("openFloor"),))
        shots = by_object(window, "floorShot")
        if shots:
            click(window, shots[0])
        QTimer.singleShot(400, after_preview)

    def after_preview():
        check("点子界面里的截图打开大图",
              window.property("previewUrl") not in ("", None),
              "previewUrl=%r" % (window.property("previewUrl"),))
        layers = by_object(window, "previewShot")
        if layers:
            click(window, layers[0])
        QTimer.singleShot(300, after_close)

    def after_close():
        check("点大图能关掉", window.property("previewUrl") == "",
              "previewUrl=%r" % (window.property("previewUrl"),))
        check("关大图不会顺手关掉子界面",
              window.property("openFloor") not in ("", None),
              "openFloor=%r" % (window.property("openFloor"),))
        closes = by_object(window, "floorClose")
        if closes:
            click(window, closes[0])
        QTimer.singleShot(300, after_sheet_close)

    def after_sheet_close():
        check("点 ✕ 关掉这一层", window.property("openFloor") == "",
              "openFloor=%r" % (window.property("openFloor"),))
        check("关子界面不会顺手退出程序", STATE["quit_at"] is None)
        finish()

    QTimer.singleShot(600, open_sheet)


def case_d(window):
    """开着「这一层」时：小窗能不能拖到主窗口外面；点 ✕ 程序退不退。"""
    def open_sheet():
        tiles = by_object(window, "mapTile")
        check("找得到地图块", len(tiles) >= 1, "count=%d" % len(tiles))
        if not tiles:
            finish()
            return
        click(window, tiles[0])
        QTimer.singleShot(500, drag_out)

    def drag_out():
        sheets = [host for host in hosts(window) if host is not window]
        check("「这一层」是一扇真窗口", len(sheets) == 1, "count=%d" % len(sheets))
        if not sheets:
            finish()
            return
        sheet = sheets[0]
        title = [i for i in walk(window) if i.objectName() == "floorTitle"
                 and shown(i)]
        if not title:
            check("找得到小窗抬头", False)
            finish()
            return
        before = (sheet.x(), sheet.y())
        # 往右下拖 320：真窗口才拖得出去（以前被钳在主窗口里）
        item = title[0]
        scene = item.mapToScene(QPoint(int(item.width() / 2),
                                       int(item.height() / 2)))
        press = QPoint(int(scene.x()), int(scene.y()))
        press_global = (sheet.x() + press.x(), sheet.y() + press.y())
        QTest.mousePress(sheet, Qt.LeftButton, Qt.NoModifier, press)
        # 一步到位（分几步发的话，窗口还在移动中，最后会多走一格）
        want = (press_global[0] + 320, press_global[1] + 80)
        point = QPoint(int(want[0] - sheet.x()), int(want[1] - sheet.y()))
        QTest.mouseMove(sheet, point)
        QGuiApplication.instance().processEvents()
        QTest.mouseRelease(sheet, Qt.LeftButton, Qt.NoModifier, point)
        QGuiApplication.instance().processEvents()
        sheet = [host for host in hosts(window) if host is not window][0]
        after = (sheet.x(), sheet.y())
        # 以前它是主窗口里的一块（340 宽的窗口里最多只能挪 36px）；
        # 现在拖多少走多少 —— 这才是"能拖到软件外面"。
        # 注意：这里用 QTest 发的是**窗口内坐标**，窗口一移动同一个坐标就被算成
        # "又挪了一段"，所以实测会走 2 倍（真鼠标给的是屏幕坐标，不会这样）；
        # 这里只断言"至少走了这么多"，别把测试工具的量法当成程序行为。
        moved = (after[0] - before[0], after[1] - before[1])
        check("小窗跟着鼠标走（不再是只能在主窗口里挪 36px）",
              moved[0] >= 300 and moved[1] >= 70,
              "before=%r after=%r moved=%r" % (before, after, moved))
        QTimer.singleShot(300, close_main)

    def close_main():
        buttons = by_object(window, "closeBtn")
        if not buttons:
            check("找到右上角的关闭按钮", False)
            finish()
            return
        click(window, buttons[0])
        STATE["click_at"] = time.time()
        QTimer.singleShot(6000, give_up)

    def give_up():
        if STATE["quit_at"] is None:
            check("开着小窗点 ✕ 也能退出程序", False, "6 秒还没退出")
            finish()

    QTimer.singleShot(600, open_sheet)
    # 看门狗：某一步抛异常时链条会断，事件循环空转看起来像"卡死"
    QTimer.singleShot(25000, give_up)


def case_c(window, controller):
    """光标在输入框里按 Esc 不退；焦点挪开再按一次才退。"""
    def focus_input():
        # 快捷键要有活动窗口才生效：屏幕外的窗口默认不是 active
        window.requestActivate()
        QGuiApplication.instance().processEvents()
        QTimer.singleShot(300, click_input)

    def click_input():
        boxes = by_object(window, "chatInput")
        check("找到输入框", len(boxes) >= 1, "count=%d" % len(boxes))
        if boxes:
            point = centre_in_window(window, boxes[0])
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QGuiApplication.instance().processEvents()
        STATE["click_at"] = time.time()
        QTest.keyClick(window, Qt.Key_Escape)
        QTimer.singleShot(500, after_first_esc)

    def after_first_esc():
        check("输入框里按 Esc 不直接退程序", STATE["quit_at"] is None,
              "程序已经退了" if STATE["quit_at"] else "还在")
        boxes = by_object(window, "chatInput")
        check("输入框还在", bool(boxes) and boxes[0].isVisible(),
              "count=%d" % len(boxes))
        if boxes:
            # 把焦点还回去（真走"点别处"这条路：点怪物行不行 —— 行上没有焦点，
            # TextInput 会一直握着 activeFocus），这里直接清焦点
            boxes[0].setProperty("focus", False)
        QGuiApplication.instance().processEvents()
        QTimer.singleShot(200, second_esc)

    def second_esc():
        STATE["click_at"] = time.time()
        QTest.keyClick(window, Qt.Key_Escape)
        QTimer.singleShot(2500, give_up)

    def give_up():
        if STATE["quit_at"] is None:
            STATE["gave_up"] = True
            check("焦点不在输入框时按 Esc 能退出程序", False, "没退")
            finish()

    check("场景 c：先点进输入框", True)
    QTimer.singleShot(600, focus_input)


def finish():
    print("\n==== 结果 ====", flush=True)
    for name, ok, detail in RESULTS:
        print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    fails = [n for n, ok, _ in RESULTS if not ok]
    print(("失败 %d 项：%s" % (len(fails), fails)) if fails else "全部通过",
          flush=True)
    APP.quit()


def main() -> int:
    global APP, ENGINE, CONTROLLER, CASE_WINDOW
    quiet_crash_dialogs()
    APP = QGuiApplication(sys.argv[:1])
    APP.setApplicationName("ChaitaAssistant")
    CONTROLLER, ENGINE, CASE_WINDOW = build()

    def on_quit():
        STATE["quit_at"] = time.time()

    APP.aboutToQuit.connect(on_quit)

    if CASE == "a":
        case_a(CASE_WINDOW)
    elif CASE == "b":
        case_b(CASE_WINDOW)
    elif CASE == "d":
        case_d(CASE_WINDOW)
    else:
        case_c(CASE_WINDOW, CONTROLLER)

    APP.exec()
    try:
        ov._teardown(APP, ENGINE, CASE_WINDOW, CONTROLLER)
    except Exception:
        pass
    # 事件循环结束后再补结论：点完到退出用了多久、退出那一刻窗口还开着吗
    if CASE == "a" and STATE["quit_at"]:
        took = STATE["quit_at"] - (STATE["click_at"] or STATE["quit_at"])
        check("点 ✕ 能退出", True, "%.2f 秒" % took)
        try:
            still_open = bool(CASE_WINDOW.isVisible())
        except RuntimeError:
            still_open = False      # 窗口对象都销毁了 = 肯定没了
        gone = (STATE["visible_at_click"] is False) or not still_open
        check("点了之后窗口立刻消失（用户能马上看到反应）", gone,
              "窗口还开着" if not gone else "已消失")
    if CASE == "c" and STATE["quit_at"] and not STATE.get("gave_up"):
        took = STATE["quit_at"] - (STATE["click_at"] or STATE["quit_at"])
        check("焦点不在输入框时按 Esc 能退出程序", True, "%.2f 秒" % took)
    if CASE == "d" and STATE["quit_at"]:
        took = STATE["quit_at"] - (STATE["click_at"] or STATE["quit_at"])
        check("开着小窗点 ✕ 也能退出程序", True, "%.2f 秒" % took)
    print("\n==== 汇总 ====", flush=True)
    fails = [n for n, ok, _ in RESULTS if not ok]
    for name, ok, detail in RESULTS:
        print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    print(("失败 %d 项：%s" % (len(fails), fails)) if fails else "全部通过",
          flush=True)
    return 9 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
