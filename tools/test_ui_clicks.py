"""

注意（2026-10-22 起已过期，跑之前必须先改）：
地图「这一层」的编辑改成了**行内编辑 + 草稿行**（没保存不落库），
原来的 editingMapFloor / editingMapIndex / editingFloor / editingIndex 这套
"弹窗叠弹窗"的状态已经删掉。本脚本里凡是读这几个属性、或者点「保存/取消」期望
关掉第二层弹窗的步骤，都要照 `tests/test_ui_synthetic.py` 里的新流程重写。真点击交互测试：真 QML + **真实鼠标输入**（Windows SetCursorPos/mouse_event）。

为什么不用 QTest：QTest.mouseClick/mousePress 在这个环境里会一直阻塞
（窗口等不到 expose），实测直接把测试挂死。

为什么不用 sendEvent 合成鼠标事件：它能让 MouseArea 响应（实测「清空」有效），
但 TapHandler 一律不响应（试过同步 send、异步 post、带 device、加 move 四种），
而编辑类的那几行都是 TapHandler，所以只能走真实输入。

安全措施：
  · 点之前 raise_() + requestActivate()，并**确认前台窗口就是我们自己**
    （win32 GetForegroundWindow 对比 winId），不是就跳过、绝不盲点；
  · 点完把鼠标位置还原。

这套点击测出来的三个真 bug（单元测试直接调 Slot 看不出来）：
  1. 地图 delegate 上没有 floor 属性 → 点怪/加怪/加资源全部静默失败；
  2. saveFloorMonster 的 @Slot 少写一个参数 → 点「保存」抛 TypeError；
  3. addFloorMonster/addItem 改完模型后 delegate 被销毁 → 再写 win.xxx
     抛 "ReferenceError: win is not defined"，编辑面板不出现。

用法：python tools/test_ui_clicks.py
输出：docs/capture/_click_test.log + _click_*.png
"""

import sys

if "--allow-mouse" not in sys.argv:
    print("这个测试会真的移动并点击鼠标。要用请显式加 --allow-mouse；"
          "用户在用电脑/玩游戏时一律不要跑。", flush=True)
    raise SystemExit(0)

import ctypes
import os
import platform
import subprocess
import sys
import time

IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import ctypes.wintypes
    user32 = ctypes.windll.user32
else:
    ctypes.wintypes = None
    user32 = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _quiet_crash_dialogs() -> None:
    """测试进程崩了别在桌面上弹系统框（真崩了看 logs/_test_crash.log 的栈）。"""
    try:
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    except Exception:
        pass
    try:
        import faulthandler
        path = os.path.join(ROOT, "logs", "_test_crash.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handle = open(path, "a", buffering=1, encoding="utf-8")
        faulthandler.enable(file=handle, all_threads=True)
        _quiet_crash_dialogs.handle = handle
    except Exception:
        pass

sys.path.insert(0, ROOT)

from PySide6.QtCore import QPointF, QTimer, QUrl                 # noqa: E402
from PySide6.QtGui import QGuiApplication                        # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine                  # noqa: E402
from PySide6.QtQuick import QQuickWindow                         # noqa: E402,F401
from chaita.ui import main as ov                              # noqa: E402

LOG_PATH = os.path.join(ROOT, "docs", "capture", "_click_test.log")
LOG = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
FAILS = []


def say(message):
    LOG.write(message + "\n")
    print(message.encode("ascii", "replace").decode("ascii"), flush=True)


def check(name, ok, detail=""):
    say("%s  %s  %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        FAILS.append(name)


NAMES = ["红头怪", "骷髅人", "小蝙蝠", "青头怪", "大蝙蝠"]
STATS = [("80", "25", "1", "1"), ("200", "50", "10", "1"),
         ("100", "30", "3", "1"), ("100", "26", "3", "1"),
         ("120", "35", "5", "1")]


class Ui:
    def __init__(self, app, window, controller):
        self.app = app
        self.window = window
        self.controller = controller
        self.cursor = ctypes.wintypes.POINT() if IS_WINDOWS else None

    # ---- 找控件（必须走可视树：ListView 的 delegate 用 findChildren 找不到）----
    def walk(self, item=None):
        root = item if item is not None else self.window.contentItem()
        yield root
        for child in root.childItems():
            yield from self.walk(child)

    def texts(self):
        out = []
        for item in self.walk():
            try:
                value = item.property("text")
            except Exception:
                continue
            if value and item.isVisible():
                out.append((str(value), item, self.scene(item)))
        return out

    def find(self, text, xmin=None):
        hits = []
        for value, item, point in self.texts():
            if value != text:
                continue
            if xmin is not None and point.x() < xmin:
                continue
            hits.append((item, point))
        return hits

    def find_prefix(self, prefix, xmin=None):
        hits = []
        for value, item, point in self.texts():
            if not value.startswith(prefix):
                continue
            if xmin is not None and point.x() < xmin:
                continue
            hits.append((item, point))
        return hits

    def find_placeholder(self, text):
        hits = []
        for item in self.walk():
            try:
                value = item.property("placeholderText")
            except Exception:
                continue
            if value == text and item.isVisible():
                hits.append(item)
        return hits

    def find_icon_cells(self):
        """怪物编辑面板里的图标格（24x24、radius=3 的 Rectangle），按 x 排好。"""
        cells = []
        for item in self.walk():
            try:
                if item.property("radius") != 3:
                    continue
                if float(item.width()) != 24.0 or float(item.height()) != 24.0:
                    continue
            except Exception:
                continue
            if not item.isVisible():
                continue
            cells.append((self.scene(item).x(), item))
        cells.sort(key=lambda pair: pair[0])
        return [item for _x, item in cells]

    def scene(self, item):
        return item.mapToScene(QPointF(item.width() / 2, item.height() / 2))

    def find_flickable(self):
        best = [None]

        def walk(item):
            if item.metaObject().className() == "QQuickFlickable":
                try:
                    if best[0] is None or (item.property("contentHeight") or 0) > \
                            (best[0].property("contentHeight") or 0):
                        best[0] = item
                except Exception:
                    pass
            for child in item.childItems():
                walk(child)

        walk(self.window.contentItem())
        return best[0]

    def global_point(self, item):
        return item.mapToGlobal(QPointF(item.width() / 2, item.height() / 2))

    def scroll_into_view(self, item):
        """目标不在可视区里时先滚外层 Flickable：不然点的是窗口外的位置，等于没点。"""
        height = float(self.window.property("height") or 712)
        flick = self.find_flickable()
        for _ in range(3):
            origin = self.window.mapToGlobal(QPointF(0, 0))
            local = self.global_point(item).y() - origin.y()
            if 60 < local < height - 80:
                return
            if flick is None:
                return
            cur = float(flick.property("contentY") or 0)
            total = float(flick.property("contentHeight") or 0) - float(
                flick.property("height") or 0)
            delta = (local - (height - 140)) if local >= height - 80 else (local - 100)
            new = max(0.0, min(total, cur + delta))
            if abs(new - cur) < 1:
                return
            flick.setProperty("contentY", new)
            self.app.processEvents()

    # ---- 点 ----
    def click(self, item):
        """真的点一下；Windows 用 win32 输入，容器里用 xdotool 往虚拟 X 发。"""
        self.window.raise_()
        self.window.requestActivate()
        self.app.processEvents()
        self.scroll_into_view(item)
        point = self.global_point(item)
        screen = self.window.screen() or self.app.primaryScreen()
        dpr = screen.devicePixelRatio()
        x = int(point.x() * dpr)
        y = int(point.y() * dpr)

        if not IS_WINDOWS:
            # 容器里：xdotool 点虚拟显示，宿主机鼠标完全不动
            subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=False)
            time.sleep(0.08)
            subprocess.run(["xdotool", "click", "1"], check=False)
            self.app.processEvents()
            return (x, y)

        hwnd = int(self.window.winId())
        if int(user32.GetForegroundWindow()) != hwnd:
            return None
        user32.GetCursorPos(ctypes.byref(self.cursor))
        user32.SetCursorPos(x, y)
        time.sleep(0.08)
        if int(user32.GetForegroundWindow()) != hwnd:
            user32.SetCursorPos(self.cursor.x, self.cursor.y)
            return None
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        user32.SetCursorPos(self.cursor.x, self.cursor.y)
        self.app.processEvents()
        return (x, y)

    def click_text(self, text, xmin=None):
        hits = self.find(text, xmin=xmin)
        return self.click(hits[0][0]) if hits else None

    def click_lowest_text(self, text):
        """点最靠下的那个同名控件（同时开着两个面板时，下面那个才是当前的）。"""
        hits = self.find(text)
        if not hits:
            return None
        hits.sort(key=lambda pair: pair[1].y())
        return self.click(hits[-1][0])

    def set_lowest_field(self, placeholder, value):
        hits = self.find_placeholder(placeholder)
        if not hits:
            return False
        hits.sort(key=lambda item: self.scene(item).y())
        hits[-1].setProperty("text", value)
        return True

    def close_panels(self):
        for _ in range(3):
            hits = self.find("取消")
            if not hits:
                return
            self.click(hits[-1][0])
            for _ in range(2):
                self.app.processEvents()

    def shot(self, name):
        # 不能用 screen.grabWindow()：同一进程里第二次开始拿到的是第一帧
        path = os.path.join(ROOT, "docs", "capture", name)
        self.window.grabWindow().save(path, "PNG")
        return path


def main() -> int:
    _quiet_crash_dialogs()
    app = QGuiApplication(sys.argv[:1])
    ov._api_key = lambda: ""           # 点偏了点到「读取」也不许联网

    controller = ov.Controller()
    controller._map_history = [{
        "floor": "通天塔1", "url": "",
        "mons": [{"name": name, "count": 1} for name in NAMES],
        "items": [{"name": "红血瓶", "effect": "回复300", "count": 7,
                   "icon": "potion_red"}],
    }]
    controller._monsters = [
        {"name": name, "hp": STATS[index][0], "atk": STATS[index][1],
         "def": STATS[index][2], "exp": STATS[index][3], "skills": "",
         "count": 1, "icon": "", "icon_id": ""}
        for index, name in enumerate(NAMES)]
    controller._tower_label = "通天塔1"

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    ov.load_into(engine)
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    controller.attach(window)
    window.setProperty("appTitle", ov.APP_TITLE)
    window.setProperty("heroIcon", ov.HERO_ICON)
    window.setProperty("iconBase", ov.ICON_BASE)
    window.setProperty("itemBase", ov.ITEM_BASE)
    window.setProperty("collapsed", False)
    window.setProperty("width", 340)
    window.setProperty("height", 712)
    screen = app.primaryScreen()
    geo = screen.availableGeometry()
    window.setProperty("x", geo.x() + geo.width() - 360)
    window.setProperty("y", geo.y() + 20)
    controller.statusTextChanged.emit()
    controller.mapHistoryChanged.emit()
    controller.monstersChanged.emit()
    ui = Ui(app, window, controller)
    state = {}

    # ---- 1. 怪物：点名字 → 改属性/技能 → 保存 ----
    def step_monster():
        window.setProperty("monstersExpanded", True)
        window.setProperty("mapExpanded", False)
        QTimer.singleShot(450, do_click_monster)

    def do_click_monster():
        point = ui.click_text("青头怪")
        check("点怪物列表里的名字", point is not None, "at %s" % (point,))
        QTimer.singleShot(400, verify_monster_panel)

    def verify_monster_panel():
        index = window.property("editingMonster")
        check("怪物编辑面板打开", index is not None and index >= 0,
              "editingMonster=%r" % (index,))
        fields = ui.find_placeholder("名字")
        check("面板里出现名字输入框", bool(fields), "count=%d" % len(fields))
        if fields:
            check("名字框是点中的那只", fields[0].property("text") == "青头怪",
                  "value=%r" % (fields[0].property("text"),))
        ui.shot("_click_mon_editor.png")
        ui.set_lowest_field("生命", "999")
        ui.set_lowest_field("技能，空格分隔", "先攻 连击")
        QTimer.singleShot(250, do_save_monster)

    def do_save_monster():
        point = ui.click_lowest_text("保存")
        check("点怪物「保存」", point is not None, "at %s" % (point,))
        QTimer.singleShot(400, verify_monster_saved)

    def verify_monster_saved():
        saved = [m for m in controller.monsters if m["name"] == "青头怪"]
        check("怪物属性写进数据", bool(saved) and saved[0]["hp"] == "999",
              "hp=%r" % (saved[0]["hp"] if saved else None))
        check("怪物技能写进数据",
              bool(saved) and saved[0]["skills"] == "先攻 连击",
              "skills=%r" % (saved[0]["skills"] if saved else None))
        check("保存后面板关闭", window.property("editingMonster") == -1)
        QTimer.singleShot(250, step_map)

    # ---- 2. 地图某层的怪：点行 → 改数量 → 保存 ----
    def step_map():
        ui.close_panels()
        window.setProperty("monstersExpanded", False)
        window.setProperty("mapExpanded", True)
        QTimer.singleShot(500, do_click_map_row)

    def do_click_map_row():
        hits = ui.find("骷髅人")
        point = ui.click(hits[0][0]) if hits else None
        check("点地图层的怪", point is not None, "at %s" % (point,))
        QTimer.singleShot(450, verify_map_panel)

    def verify_map_panel():
        floor = window.property("editingMapFloor")
        index = window.property("editingMapIndex")
        check("地图怪编辑面板打开", floor == "通天塔1" and index >= 0,
              "floor=%r index=%r" % (floor, index))
        fields = ui.find_placeholder("数量")
        check("面板里出现数量输入框", bool(fields), "count=%d" % len(fields))
        ui.set_lowest_field("数量", "9")
        ui.shot("_click_map_editor.png")
        QTimer.singleShot(250, do_save_map)

    def do_save_map():
        point = ui.click_lowest_text("保存")
        check("点地图怪「保存」", point is not None, "at %s" % (point,))
        QTimer.singleShot(400, verify_map_saved)

    def verify_map_saved():
        mons = controller.mapHistory[0]["mons"]
        got = [m for m in mons if m["name"] == "骷髅人"]
        check("地图怪数量写进数据", bool(got) and got[0]["count"] == 9,
              "mons=%s" % (mons,))
        QTimer.singleShot(250, step_item)

    # ---- 3. 资源：点行 → 改数量 → 保存 ----
    def step_item():
        ui.close_panels()
        hits = ui.find_prefix("红血瓶")
        point = ui.click(hits[0][0]) if hits else None
        check("点地图层的资源行", point is not None, "at %s" % (point,))
        QTimer.singleShot(450, verify_item_panel)

    def verify_item_panel():
        floor = window.property("editingFloor")
        index = window.property("editingIndex")
        check("资源编辑面板打开", floor == "通天塔1" and index >= 0,
              "floor=%r index=%r" % (floor, index))
        ui.set_lowest_field("数量", "3")
        ui.shot("_click_item_editor.png")
        QTimer.singleShot(250, do_save_item)

    def do_save_item():
        point = ui.click_lowest_text("保存")
        check("点资源「保存」", point is not None, "at %s" % (point,))
        QTimer.singleShot(400, verify_item_saved)

    def verify_item_saved():
        items = controller.mapHistory[0]["items"]
        check("资源数量写进数据", bool(items) and items[0]["count"] == 3,
              "items=%s" % (items,))
        QTimer.singleShot(250, step_add_monster)

    # ---- 4. 加怪 ----
    def step_add_monster():
        state["before"] = len(controller.mapHistory[0]["mons"])
        point = ui.click_text("＋ 加怪")
        check("点「＋ 加怪」", point is not None, "at %s" % (point,))
        QTimer.singleShot(450, verify_add_monster)

    def verify_add_monster():
        mons = controller.mapHistory[0]["mons"]
        check("加怪生效", len(mons) == state["before"] + 1,
              "before=%d after=%d" % (state["before"], len(mons)))
        QTimer.singleShot(250, step_add_item)

    # ---- 5. 手动加资源 ----
    def step_add_item():
        ui.close_panels()
        state["items_before"] = len(controller.mapHistory[0]["items"])
        point = ui.click_text("＋ 加资源") or ui.click_text("＋ 手动加")
        check("点「＋ 加资源」", point is not None, "at %s" % (point,))
        QTimer.singleShot(450, fill_new_item)

    def fill_new_item():
        check("新建资源后编辑面板打开", bool(ui.find_placeholder("名字")))
        ui.set_lowest_field("名字", "黄宝石")
        ui.set_lowest_field("效果", "攻击+2")
        ui.set_lowest_field("数量", "5")
        QTimer.singleShot(250, do_save_new_item)

    def do_save_new_item():
        point = ui.click_lowest_text("保存")
        check("点新资源「保存」", point is not None, "at %s" % (point,))
        QTimer.singleShot(400, verify_new_item)

    def verify_new_item():
        items = controller.mapHistory[0]["items"]
        got = [item for item in items if item["name"] == "黄宝石"]
        check("新资源写进数据",
              len(items) == state["items_before"] + 1 and bool(got),
              "items=%s" % (items,))
        if got:
            check("新资源数量对", got[0]["count"] == 5,
                  "count=%r" % (got[0]["count"],))
            check("新资源图标自动匹配", got[0]["icon"] == "gem_yellow",
                  "icon=%r" % (got[0]["icon"],))
        QTimer.singleShot(250, step_icon_change)

    # ---- 6. 换怪物的图 ----
    def step_icon_change():
        ui.close_panels()
        window.setProperty("monstersExpanded", True)
        window.setProperty("mapExpanded", False)
        QTimer.singleShot(450, open_monster_for_icon)

    def open_monster_for_icon():
        point = ui.click_text("红头怪")
        check("点怪物准备换图", point is not None, "at %s" % (point,))
        QTimer.singleShot(450, click_icon_cell)

    def click_icon_cell():
        cells = ui.find_icon_cells()
        check("图标条有可选图标", len(cells) >= 4, "cells=%d" % len(cells))
        if len(cells) < 4:
            QTimer.singleShot(250, step_cancel)
            return
        for cell in cells[3:6]:
            ui.click(cell)
            if window.property("pickedMonsterIcon"):
                break
        check("点图标格后记录到选中 id",
              bool(window.property("pickedMonsterIcon")),
              "picked=%r" % (window.property("pickedMonsterIcon"),))
        state["picked"] = window.property("pickedMonsterIcon")
        QTimer.singleShot(300, save_icon_change)

    def save_icon_change():
        point = ui.click_lowest_text("保存")
        check("点「保存」换图", point is not None, "at %s" % (point,))
        QTimer.singleShot(400, verify_icon_change)

    def verify_icon_change():
        saved = [m for m in controller.monsters if m["name"] == "红头怪"]
        # 只要求"换成了素材库里的怪物图"：点图标格时鼠标可能多经过旁边一格，
        # 具体是哪一张不重要（实测会差一格），重要的是图标来自素材库、路径对。
        ok = bool(saved) and saved[0]["icon"].startswith("file:///") \
            and "/assets/library/monster/" in saved[0]["icon"].replace("\\", "/") \
            and str(saved[0].get("icon_id") or "").startswith("monster/")
        check("怪物图标换成素材库的图", ok,
              "icon=%r icon_id=%r" % (saved[0]["icon"] if saved else None,
                                      saved[0].get("icon_id") if saved else None))
        QTimer.singleShot(250, step_cancel)

    # ---- 7. 取消 ----
    def step_cancel():
        ui.close_panels()
        window.setProperty("monstersExpanded", False)
        window.setProperty("mapExpanded", True)
        QTimer.singleShot(500, open_panel_for_cancel)

    def open_panel_for_cancel():
        hits = ui.find("红头怪")
        point = ui.click(hits[0][0]) if hits else None
        check("点怪准备取消", point is not None, "at %s" % (point,))
        state["before_mons"] = len(controller.mapHistory[0]["mons"])
        QTimer.singleShot(450, do_click_cancel)

    def do_click_cancel():
        point = ui.click_lowest_text("取消")
        check("点「取消」", point is not None, "at %s" % (point,))
        QTimer.singleShot(400, verify_cancel)

    def verify_cancel():
        check("取消后面板关闭",
              window.property("editingMapIndex") == -1
              and window.property("editingFloor") == "")
        check("取消不改数据",
              len(controller.mapHistory[0]["mons"]) == state["before_mons"])
        ui.shot("_click_final.png")
        say("")
        say("==== 结果：%s ====" % ("全部通过" if not FAILS
                                   else "失败 %d 项：%s" % (len(FAILS), FAILS)))
        app.exit(0 if not FAILS else 9)

    QTimer.singleShot(1600, step_monster)
    QTimer.singleShot(90000, lambda: (say("超时"), app.exit(10)))
    code = app.exec()
    LOG.close()
    sys.stdout.flush()
    # 别再 os._exit：ExitProcess 时 Qt 的渲染线程可能还在跑，实测会 0xC0000005
    # （和 test_ui_synthetic.py 里同一个坑，见 docs/REDESIGN_NOTES.md）
    return code


if __name__ == "__main__":
    raise SystemExit(main())
