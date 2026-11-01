"""不用真鼠标的界面自检：合成鼠标/键盘事件直接送进 QML 窗口，逐项确认。

为什么留它（和 tools/test_ui_clicks.py 的分工）：
  - 真鼠标点击测试只有在窗口能拿到前台时才准；桌面被别的程序占着时，
    点击会落到别的程序上，跑起来不可靠。
  - 这里用 QGuiApplication.sendEvent 往窗口里送 QMouseEvent / QKeyEvent，
    MouseArea 会响应；界面里全是 MouseArea（没有 TapHandler），所以测得到。

覆盖的是 v12「塔级总览」这一版（用户拍板的设计，见 docs/DESIGN.md）：
  · 结构：地图 / 怪物 / 技能 / 对话，没有资源分区；
  · 读取按钮在地图那一侧（用户："不要放在对话框里"），点它真的起一次读取；
  · 塔级汇总常驻可见：几只、剩几只、带某个技能的怪还有多少；
  · 怪物一行一个、技能一行一个，都不带层号、不列怪名；
  · 输入 → 发送 → 进对话历史，回车也能发；
  · 折叠 / 展开、点地图看大图、内容超出时滚动。
"""

import io
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# 自检不该占用用户的窗口状态（否则最后一次的尺寸会污染下一次渲染）
os.environ["CHAITA_NO_UI_STATE"] = "1"

import cv2                                              # noqa: E402
import numpy as np                                      # noqa: E402
from PySide6.QtCore import (QEvent, QPoint, QPointF, QTimer,  # noqa: E402
                            Qt, QUrl)
from PySide6.QtGui import (QGuiApplication, QKeyEvent,      # noqa: E402
                           QMouseEvent)
from PySide6.QtQml import QQmlApplicationEngine          # noqa: E402
from PySide6.QtQuick import QQuickWindow                 # noqa: E402,F401
from PySide6.QtTest import QTest                         # noqa: E402

from chaita.ui import main as ov                      # noqa: E402

# 中文控制台是 GBK：检查项名里带 "✕" 这种符号时 print 会直接抛 UnicodeEncodeError，
# 整个自检半路中断，看起来像界面回归。把输出流固定成 UTF-8，别让编码问题冒充功能问题。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOG_PATH = os.path.join(ROOT, "docs", "capture", "_synthetic.log")
SAMPLE = os.path.join(ROOT, "docs", "capture", "h5_miaomiao_212609.png")

LOG = None
FAILED = []
STATE = {}
app = None

# 手算好的真值（fixture 见 main()）：
#   红头怪 2+2（其中 2 只已打完，剩 2）、骷髅人 1、地图怪 4
#   → 3 种 / 共 9 只 / 剩 7
#   先攻：红头怪 4 + 骷髅人 1 = 5 只，剩 2+1 = 3；坚固：骷髅人 1 只，剩 1
WANT_MON_AGG = "3 种 · 共 9 只 · 剩 7"
WANT_SKILL_AGG = "2 种 · 涉及 5 只"


def check(name, ok, detail=""):
    """一条检查：写进日志、打到 stdout，不通过就记下来。"""
    line = ("PASS  %s" % name) if ok else ("FAIL  %s" % name)
    if detail:
        line += "   " + str(detail)
    LOG.write(line + "\n")
    LOG.flush()
    print(line, flush=True)
    if not ok:
        FAILED.append(name)
    return bool(ok)


def next_step(delay, func):
    QTimer.singleShot(delay, func)


def done(code=None):
    ok = not FAILED
    LOG.write("\n==== 结果：%s ====\n"
              % ("全部通过" if ok else "有 %d 项不通过：%s"
                 % (len(FAILED), "；".join(FAILED[:8]))))
    LOG.flush()
    print("==== 结果：%s ====" % ("全部通过" if ok else "不通过 %d 项" % len(FAILED)),
          flush=True)
    STATE["code"] = code if code is not None else (0 if ok else 1)
    app.quit()


def _save_thumb() -> str:
    """拿一张真实截图当缩略图（缩到 200 宽，只缩不放）。

    **先按塔的区域裁成地图**：真实「读地图」存下来的只有地图那一块，没有左边的人物
    面板和浏览器标签栏（用户："你测试用的地图都带人物信息，实际根本不可能"）。
    """
    from chaita.game import read as game_read
    from chaita.game import towers
    if not os.path.exists(SAMPLE):
        return ""
    image = cv2.imdecode(np.fromfile(SAMPLE, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return ""
    shot = game_read.map_snapshot(towers.H5_MOTA, image)
    if shot is None or not getattr(shot, "size", 0):
        return ""
    return ov._save_thumb(shot, "synthetic_thumb", width=200)


def _sprite(name: str) -> str:
    """真实怪物图（自检里要看缩略图，不能拿空字符串糊弄）。

    素材库的文件名是「编号_种族_英文名.png」，**编号会随建库重排**——所以按
    `_英文名` 这个后缀找，别写死编号。写死的后果都见过一次：素材库重排之后这里
    悄悄返回 ""，"怪行/编辑界面有缩略图"两条自检就红了，看着像界面坏了。
    """
    folder = os.path.join(ROOT, "assets", "library", "monster")
    exact = os.path.join(folder, name)
    if os.path.exists(exact):
        return "file:///" + exact.replace("\\", "/")
    stem = name[:-4] if name.lower().endswith(".png") else name
    hits = sorted(f for f in os.listdir(folder)
                  if f.lower().endswith("_" + stem.lower() + ".png"))
    if not hits:
        return ""
    return "file:///" + os.path.join(folder, hits[0]).replace("\\", "/")


def main() -> int:
    global LOG, app
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    LOG = io.open(LOG_PATH, "w", encoding="utf-8")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    thumb_url = _save_thumb()
    controller = ov.Controller()
    # 读取/对话都是起线程干的：自检只验界面这一侧，别真去抓用户的窗口。
    # _start_task / sendChat 内部走 self._start_thread，在实例上盖掉它就能拦住。
    controller._start_thread = lambda *args, **kwargs: None
    controller._map_history = [
        {"floor": "通天塔1", "url": thumb_url, "mons": [
            {"name": "红头怪", "count": 2},
            {"name": "骷髅人", "count": 1},
        ], "items": [{"name": "红血瓶", "effect": "体力 +150", "count": 7,
                      "icon": "potion_red"}]},
        {"floor": "通天塔2", "url": thumb_url, "mons": [
            {"name": "红头怪", "count": 2, "done": True},
            {"name": "地图怪", "count": 4},
        ], "items": []},
    ]
    controller._monsters = [
        {"name": "红头怪", "hp": "80", "atk": "25", "def": "1", "gold": "12",
         "exp": "1",
         "skills": "先攻", "skill_items": [{"name": "先攻", "value": ""}],
         "count": 2, "icon": _sprite("fairy_dark_sprite.png")},
        {"name": "骷髅人", "hp": "120", "atk": "30", "def": "5", "exp": "3",
         "skills": "先攻 坚固",
         "skill_items": [{"name": "先攻", "value": ""},
                         {"name": "坚固", "value": ""}],
         "count": 1, "icon": _sprite("undead_spirit_warrior.png")},
        # 手册里读过、地图上没加过：塔级列表里不该出现
        {"name": "手册怪", "hp": "9", "atk": "9", "def": "9", "exp": "9",
         "skills": "先攻", "skill_items": [{"name": "先攻", "value": ""}],
         "count": 0, "icon": ""},
    ]
    # 技能下拉的候选（不依赖磁盘上的技能表，测试要确定）
    controller._skill_catalog = ["先攻", "坚固", "连击", "破甲", "吸血"]
    controller._tasks = [{"id": 1, "state": "done", "text": "通天塔1",
                          "mode": "map", "started": time.time() - 120}]
    # 任务号接着往下发：不设的话点「读取」会再拿到 id=1，和上面这条撞号
    controller._task_seq = 5
    controller._last_status = {"hp": "1200", "atk": "60", "def": "20", "mdef": "5",
                               "level": "12", "exp": "3400", "gold": "9800",
                               "next": "12000",
                               "keys": {"yellow": 4, "blue": 2, "red": 1, "green": 0},
                               "special": {"po": 1, "zha": 2, "fei": 0}}
    controller._apply_status(controller._last_status)
    controller._tower_label = "坐牢成仙 通天塔1"
    controller._chat_log = [
        {"who": "你", "text": "红头怪还剩几只？", "at": "14:31"},
        {"who": "AI", "text": "通天塔1 还有 2 只，通天塔2 打完。", "at": "14:31"},
    ]

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    ov.load_into(engine)
    if not engine.rootObjects():
        LOG.write("QML 加载失败\n")
        done(1)
        return 1
    window = engine.rootObjects()[0]
    controller.attach(window)
    window.setProperty("appTitle", ov.APP_TITLE)
    window.setProperty("heroIcon", ov.HERO_ICON)
    window.setProperty("iconBase", ov.ICON_BASE)
    window.setProperty("itemBase", ov.ITEM_BASE)
    window.setProperty("collapsed", False)
    window.setProperty("x", -6000)
    window.setProperty("y", -6000)
    window.show()
    # Esc 走的是 QML Shortcut：Qt Quick 只给"活动窗口"投递快捷键，
    # 不激活的话合成按键会被静默忽略（实测：requestActivate 之后就正常了）
    window.requestActivate()
    app.processEvents()
    controller.statusTextChanged.emit()
    controller.mapHistoryChanged.emit()
    controller.monstersChanged.emit()
    controller.tasksChanged.emit()
    controller.chatLogChanged.emit()

    # ---------------- 工具 ----------------
    def host_windows():
        """主窗口 + 它开出来的真窗口（「这一层」/ 伤害计算）。"""
        hosts = [window]
        try:
            names = window.property("floorWindows")
            names = names.toVariant() if hasattr(names, "toVariant") else names
            for name in names or []:
                sheet = window.floorSheetOf(str(name))
                if sheet is not None:
                    hosts.append(sheet)
            battle = window.property("battleWindow")
            if hasattr(battle, "toQObject"):
                battle = battle.toQObject()
            if battle is not None:
                hosts.append(battle)
        except (RuntimeError, AttributeError):
            pass
        return hosts

    def window_of(item):
        node = item
        while node is not None:
            for host in host_windows():
                if node is host.contentItem():
                    return host
            node = node.parentItem()
        return window

    def walk():
        out = []
        for host in host_windows():
            stack = list(host.contentItem().childItems())
            while stack:
                node = stack.pop()
                out.append(node)
                stack.extend(node.childItems())
        return out

    def shown(item):
        """真的显示着：自己 + 一路 parent 的 visible / opacity 都要算。"""
        node = item
        while node is not None:
            try:
                if not node.isVisible():
                    return False
                if float(node.property("opacity") or 1) <= 0.01:
                    return False
            except Exception:
                pass
            node = node.parentItem()
        return True

    def plain(text):
        return re.sub(r"<[^>]+>", "", str(text or "")).strip()

    def is_text(item):
        """是不是一段文字（delegate 里的 Text 会被编成 QQuickText_QML_x 子类）。"""
        name = item.metaObject().className()
        return (name.startswith("QQuickText")
                and "Input" not in name and "Edit" not in name)

    def find(needle):
        return [item for item in walk()
                if is_text(item) and shown(item)
                and needle in plain(item.property("text"))]

    def find_object(name):
        for item in walk():
            if item.objectName() == name and shown(item):
                return item
        return None

    def find_all(name):
        # 按屏幕上的上下顺序给（walk 是深度优先，顺序和界面先后不一致）
        items = [item for item in walk()
                 if item.objectName() == name and shown(item)]
        return sorted(items, key=lambda item: item.mapToScene(QPointF(0, 0)).y())

    def inside(name):
        root = find_object(name)
        if root is None:
            return []
        out, stack = [], list(root.childItems())
        while stack:
            node = stack.pop()
            out.append(node)
            stack.extend(node.childItems())
        return out

    def row_texts(row):
        out, stack = [], list(row.childItems())
        while stack:
            node = stack.pop()
            if is_text(node) and shown(node):
                out.append(plain(node.property("text")))
            stack.extend(node.childItems())
        return out

    def texts_inside(name):
        root = find_object(name)
        if root is None:
            return []
        out, stack = [], list(root.childItems())
        while stack:
            node = stack.pop()
            if is_text(node) and shown(node):
                out.append(plain(node.property("text")))
            stack.extend(node.childItems())
        return out

    def _mouse_event(kind, point, button, buttons):
        global_pos = window.mapToGlobal(QPoint(int(point.x()), int(point.y())))
        return QMouseEvent(kind, point, QPointF(global_pos), button, buttons,
                           Qt.NoModifier)

    def click(item, fx=0.5, fy=0.5):
        if item is None:
            return False
        target = window_of(item)
        point = item.mapToScene(QPointF(item.width() * fx, item.height() * fy))
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            app.sendEvent(target, _mouse_event(kind, point, Qt.LeftButton,
                                               Qt.LeftButton))
        app.processEvents()
        return True

    def drag(item, dx, dy):
        """按住这个控件往右下拖（合成鼠标事件，等价于用鼠标拖窗口）。

        小窗是真窗口，拖的时候窗口跟着鼠标走：每一步都按"鼠标该在哪"换算回窗口内
        坐标，不然窗口一动同一个坐标就变成"又挪了一段"，位移会被放大。
        """
        target = window_of(item)
        press = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        press_global = QPointF(target.x() + press.x(), target.y() + press.y())
        app.sendEvent(target, QMouseEvent(QEvent.MouseButtonPress, press,
                                          press_global, Qt.LeftButton,
                                          Qt.LeftButton, Qt.NoModifier))
        point = press
        for step in range(1, 5):
            want = QPointF(press_global.x() + dx * step / 4.0,
                           press_global.y() + dy * step / 4.0)
            point = QPointF(want.x() - target.x(), want.y() - target.y())
            app.sendEvent(target, QMouseEvent(QEvent.MouseMove, point, want,
                                              Qt.NoButton, Qt.LeftButton,
                                              Qt.NoModifier))
            app.processEvents()
        app.sendEvent(target, QMouseEvent(QEvent.MouseButtonRelease, point,
                                          point, Qt.LeftButton, Qt.NoButton,
                                          Qt.NoModifier))
        app.processEvents()

    def type_ascii(text):
        for ch in text:
            key = getattr(Qt, "Key_" + ch.upper(), None)
            if key is None:
                continue
            QTest.keyClick(window, key)
        app.processEvents()

    def stub_system_cursor(logical_y, down=True):
        """拖拽排序读的是**系统光标**：这里把光标钉住，并假装鼠标一直按着。

        返回恢复函数（跑完要还原，别影响后面的真实点击检查）。
        """
        from chaita.ui.controller import monsters as monsters_mod

        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        physical = int(logical_y * dpr)
        old_pos = monsters_mod._cursor_pos
        old_down = monsters_mod._cursor_down
        monsters_mod._cursor_pos = lambda: (0, physical)
        monsters_mod._cursor_down = lambda: bool(down)

        def restore():
            monsters_mod._cursor_pos = old_pos
            monsters_mod._cursor_down = old_down

        return restore

    def drag_row_slow(item, dy, steps=4):
        """按住一行往下拖：每挪一步都等一会儿，让 Python 的 40ms 计时器跑一拍。"""
        start = item.mapToScene(QPointF(item.width() / 2, 18))
        point = QPointF(start.x(), start.y())
        app.sendEvent(window, _mouse_event(QEvent.MouseButtonPress, point,
                                           Qt.LeftButton, Qt.LeftButton))
        app.processEvents()
        for step in range(1, steps + 1):
            moved = QPointF(start.x(), start.y() + dy * step / steps)
            app.sendEvent(window, _mouse_event(QEvent.MouseMove, moved,
                                               Qt.NoButton, Qt.LeftButton))
            app.processEvents()
            time.sleep(0.06)       # 让 40ms 的计时器真的跑一拍
            app.processEvents()
        end = QPointF(start.x(), start.y() + dy)
        app.sendEvent(window, _mouse_event(QEvent.MouseButtonRelease, end,
                                           Qt.LeftButton, Qt.NoButton))
        app.processEvents()

    def press(key, text=""):
        """直接往窗口送一个按键。

        QTest.keyClick(window, ...) 会走平台的按键分发（要求窗口是前台窗口），
        窗口摆在屏幕外时 Enter/Esc 这种非字符键会丢；sendEvent 是同步直投。
        """
        # QML 的 Shortcut 只对"活动窗口"生效：离屏窗口要先抢一下激活，
        # 否则 Esc 会被静默丢掉（实测 check_close 的 c 场景也是这样处理的）
        if not window.isActive():
            window.requestActivate()
            app.processEvents()
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            app.sendEvent(window, QKeyEvent(kind, key, Qt.NoModifier, text))
        app.processEvents()

    def scene_y(item):
        return item.mapToScene(QPointF(0, 0)).y()

    def scene_x(item):
        return item.mapToScene(QPointF(0, 0)).x()

    def mon_skills():
        """window.monSkills 是 QJSValue（不是 python list），先摊平。"""
        value = window.property("monSkills")
        value = value.toVariant() if hasattr(value, "toVariant") else value
        return value or []

    def content_height():
        return float(window.property("expandedHeight") or 0)

    # ---------------- 1. 结构 ----------------
    def step_structure():
        labels = [plain(i.property("text")) for i in walk()
                  if is_text(i) and shown(i)]
        check("地图/怪物/技能三个分区标题都在",
              all(x in labels for x in ("地图", "怪物", "技能")),
              "labels=%r" % ([x for x in labels if x in ("地图", "怪物", "技能")],))
        check("没有资源分区（用户：不需要资源）", "资源" not in labels)
        check("底下有对话卡", find_object("chatBar") is not None)
        # 导航条（软件名 + 关闭）和状态行（数值 + 钥匙）分开：用户嫌"血量钥匙"位置不合理
        nav = texts_inside("topBar")
        check("导航条上有软件名", any("拆塔辅助" in t for t in nav),
              "topBar=%r" % (nav,))
        check("导航条不再混进钥匙/血量",
              not any(x in " ".join(nav) for x in ("1200", "9800")),
              "topBar=%r" % (nav,))
        check("导航条上有刷新状态按钮", find_object("statusRefresh") is not None)
        check("导航条上有关闭按钮", find_object("closeBtn") is not None)
        # 用户："刷新不要单独一行"：↻ 和软件名/关闭在同一行（导航条里）
        bar_y = scene_y(find_object("topBar"))
        refresh = find_object("statusRefresh")
        check("刷新和导航条在同一行（没有单占一行）",
              refresh is not None
              and abs(scene_y(refresh) - bar_y) < 22
              and scene_y(refresh) < scene_y(find_object("statusRow")),
              "refresh_y=%.0f bar_y=%.0f" % (scene_y(refresh) if refresh else -1,
                                             bar_y))
        # 用户吐槽过："鼠标移到顶部导航栏会变手" —— 铬件不是按钮，默认得是箭头
        drag = find_object("dragArea")
        check("抬头默认是普通箭头光标（不是手）",
              drag is not None and drag.property("cursorShape") == Qt.ArrowCursor,
              "cursor=%r" % (drag.property("cursorShape") if drag else None,))
        check("抬头显示塔名", any("坐牢成仙" in t for t in texts_inside("header")),
              "header=%r" % (texts_inside("header"),))
        # 状态区分两行：血/攻/防/魔防 一行，金币 + 四色钥匙 一行
        first_line = texts_inside("statChips")
        second_line = texts_inside("resChips")
        check("第一行是生命/攻击/防御/魔防",
              all(x in first_line for x in ("1200", "60", "20", "5")),
              "statChips=%r" % (first_line,))
        check("第二行是金币 + 四色钥匙",
              "9800" in second_line
              and all(x in second_line for x in ("4", "2", "1", "0")),
              "resChips=%r" % (second_line,))
        check("钥匙和数值不在同一行（分了两行）",
              scene_y(find_object("resChips"))
              > scene_y(find_object("statChips")) + 8,
              "stat_y=%.0f res_y=%.0f"
              % (scene_y(find_object("statChips")),
                 scene_y(find_object("resChips"))))
        check("状态区在塔名下面",
              scene_y(find_object("statusRow")) > scene_y(find_object("header")),
              "status=%.0f header=%.0f"
              % (scene_y(find_object("statusRow")),
                 scene_y(find_object("header"))))

        map_btn = find_object("readMap")
        mon_btn = find_object("readMon")
        dock = find_object("chatBar")
        mon_row = find_object("monRow")
        check("地图栏和怪物栏各有一个「读取」",
              map_btn is not None and mon_btn is not None)
        if map_btn is not None and mon_btn is not None and dock is not None \
                and mon_row is not None:
            check("两个「读取」都在对话卡之外，地图那个在怪物行上方",
                  scene_y(map_btn) < scene_y(mon_row) < scene_y(dock)
                  and scene_y(map_btn) < scene_y(mon_btn),
                  "map=%.0f mon=%.0f row=%.0f dock=%.0f"
                  % (scene_y(map_btn), scene_y(mon_btn), scene_y(mon_row),
                     scene_y(dock)))

        # 对话区不许有"默认提示"（用户："默认提示都删掉，真low"）
        labels_join = " ".join(labels)
        check("对话/输入框没有默认提示文案",
              "问一句" not in labels_join and "打了血蚊" not in labels_join,
              "labels=%r" % ([t for t in labels if "问" in t or "血蚊" in t],))

        height = window.height()
        check("窗口高度由内容撑出来（不是写死的 712）",
              400 < height < 760 and abs(height - content_height()) <= 2,
              "height=%.0f expandedHeight=%.0f" % (height, content_height()))
        next_step(250, step_resize)

    # ---------------- 1.5 窗口能拉：拉过之后别被内容高度顶回去 ----------------
    def step_resize():
        window.resize(400, 640)
        app.processEvents()
        check("能把窗口拉大（不用等读到数据）",
              abs(window.height() - 640) <= 2 and window.width() == 400,
              "size=%dx%d" % (window.width(), window.height()))
        controller.mapHistoryChanged.emit()
        app.processEvents()
        check("拉过之后数据变了也不顶回去",
              abs(window.height() - 640) <= 2 and window.width() == 400,
              "size=%dx%d" % (window.width(), window.height()))
        window.forgetManualSize()
        app.processEvents()
        check("放开手动尺寸后回到内容高度",
              abs(window.height() - content_height()) <= 2,
              "height=%.0f want=%.0f" % (window.height(), content_height()))
        next_step(200, step_nothing)

    # v12 里没有"进度/清单"这类主角面板：这里反过来查它不该出现
    def step_nothing():
        labels = [plain(i.property("text")) for i in walk()
                  if is_text(i) and shown(i)]
        check("没有把「本层进度」当主角（设计约定）",
              not any(x in labels for x in ("本层", "进度", "任务")))
        next_step(150, step_monsters)

    # ---------------- 2. 怪物：一行一个、塔级汇总 ----------------
    def step_monsters():
        rows = find_all("monRow")
        check("怪物一行一个（手册读到的 + 地图上有的）", len(rows) == 4,
              "rows=%d" % len(rows))
        names = [text for row in rows for text in row_texts(row)]
        check("手册里读到、地图上还没记的怪也列出来", "手册怪" in names,
              "texts=%r" % (names,))
        joined = " ".join(" ".join(row_texts(row)) for row in rows)
        check("怪物行有 ×N（整塔总只数）", "×4" in joined and "×1" in joined,
              "text=%r" % (joined,))
        check("怪物行有「剩 N」", "剩 4" in joined and "剩 2" in joined,
              "text=%r" % (joined,))
        check("怪物行有生命/攻/防", "生命 80" in joined and "攻 25" in joined,
              "text=%r" % (joined,))
        check("怪物行不带层号", "通天塔" not in joined and "层" not in joined,
              "text=%r" % (joined,))
        check("怪物汇总常驻可见（不用搜索）",
              find(WANT_MON_AGG) != [], "want=%r" % (WANT_MON_AGG,))
        next_step(150, step_monster_drag)

    # ---------------- 2.5 怪物行：拖动排序 + 行尾删除 ----------------
    def step_monster_drag():
        rows = find_all("monRow")
        check("怪物至少两行（够拖）", len(rows) >= 2, "rows=%d" % len(rows))
        check("每行最右边都有一个删除按钮",
              len(find_all("monDeleteRow")) == len(rows),
              "buttons=%d rows=%d" % (len(find_all("monDeleteRow")), len(rows)))
        before = [m["name"] for m in controller._monsters]
        first = rows[0]
        # Python 按"第一行的屏幕 y + 行高"算落点，这里把光标钉在第二行中间
        top = window.y() + first.mapToScene(QPointF(0, 0)).y()
        restore = stub_system_cursor(top + 36 * 1.5)
        try:
            drag_row_slow(first, 40)
        finally:
            restore()
        after = [m["name"] for m in controller._monsters]
        check("拖一行能改顺序（自己排的顺序说了算）",
              after != before and after[:2] == [before[1], before[0]],
              "before=%r after=%r" % (before, after))
        check("界面上也按新顺序排",
              before[1] in row_texts(find_all("monRow")[0]),
              "first_row=%r" % (row_texts(find_all("monRow")[0]),))
        check("拖动没顺带打开编辑界面", window.property("monEdit") == -1,
              "monEdit=%r" % (window.property("monEdit"),))
        controller.moveMonster(1, 0)      # 收工：还原顺序，不影响后面的检查
        app.processEvents()
        next_step(200, step_monster_delete)

    def step_monster_delete():
        rows = find_all("monRow")
        target = None
        for button in find_all("monDeleteRow"):
            row = button.parentItem()
            if any("手册怪" in text for text in row_texts(row)):
                target = button
        check("找得到「手册怪」那一行的 ✕", target is not None)
        before_rows = len(rows)
        before_manual = len(controller._monsters)
        click(target)
        app.processEvents()
        check("点行尾的 ✕ 能删掉这只",
              len(controller._monsters) == before_manual - 1
              and len(find_all("monRow")) == before_rows - 1,
              "manual=%d rows=%d" % (len(controller._monsters),
                                     len(find_all("monRow"))))
        check("删掉的那只不在名单里了",
              "手册怪" not in [m["name"] for m in controller._monsters],
              "names=%r" % ([m["name"] for m in controller._monsters],))
        next_step(150, step_skills)

    # ---------------- 3. 技能：一行一个、不列怪名 ----------------
    def step_skills():
        rows = find_all("skillRow")
        check("技能一行一个", len(rows) == 2, "rows=%d" % len(rows))
        first = row_texts(rows[0]) if rows else []
        count_texts = [t for t in first if "只" in t and "剩" in t]
        name_texts = [t for t in first if t and t not in count_texts]
        check("技能行只有「名字 + N 只 · 剩 M」",
              len(count_texts) == 1 and len(name_texts) == 1,
              "row=%r" % (first,))
        check("技能行不列带这个技能的怪名",
              not any("头怪" in text or "骷髅" in text for text in first),
              "row=%r" % (first,))
        join = " ".join(" ".join(row_texts(row)) for row in rows)
        check("带某技能的怪还剩多少只写得出来",
              "5 只 · 剩 3" in join and "1 只 · 剩 1" in join,
              "text=%r" % (join,))
        check("技能汇总常驻可见", find(WANT_SKILL_AGG) != [],
              "want=%r" % (WANT_SKILL_AGG,))
        next_step(150, step_read)

    # ---------------- 4. 两个读取按钮：各读各的、能并行 ----------------
    def running():
        return [t for t in controller.tasks if t.get("state") == "running"]

    def step_read():
        check("读之前 controller 不在读取态", controller.reading is False)
        before = len(find_all("taskRow"))
        click(find_object("readMon"))
        check("点怪物栏的「读取」= 只读怪物手册",
              window.property("readingMode") == "monsters" and controller.reading is True
              and [t.get("mode") for t in running()] == ["monsters"],
              "mode=%r running=%r"
              % (window.property("readingMode"),
                 [(t.get("mode"), t.get("state")) for t in controller.tasks]))
        check("读取记录里多了一条", len(find_all("taskRow")) == before + 1,
              "rows=%d" % len(find_all("taskRow")))
        next_step(350, verify_reading_ui)

    def verify_reading_ui():
        check("「读取」按钮的字不变成状态（翻页还要点它）",
              texts_inside("readMon") == ["读取"],
              "labels=%r" % (texts_inside("readMon"),))
        check("在读的时候按钮右上角有小点",
              find_object("monBusyDot") is not None)
        check("地图栏按钮也一直是「读取」（各管各的）",
              texts_inside("readMap") == ["读取"],
              "labels=%r" % (texts_inside("readMap"),))
        tip = [plain(i.property("text")) for i in walk()
               if i.objectName() == "readTip" and shown(i)]
        check("读取中不重复写「读取中」（按钮上一处就够了）",
              not any("读取中" in t for t in tip), "tip=%r" % (tip,))
        check("读取中不再显示上一次的读取时间",
              not any(":" in t for t in tip), "tip=%r" % (tip,))
        check("记录里这条标着读的是手册",
              any("手册" in t for row in find_all("taskRow")
                  for t in row_texts(row)),
              "rows=%r" % ([row_texts(row) for row in find_all("taskRow")],))
        check("跑着的任务能取消", find_object("taskCancel") is not None)
        next_step(200, step_parallel)

    # 并行：地图那栏再点一次，两条任务同时在跑
    def step_parallel():
        click(find_object("readMap"))
        modes = sorted(t.get("mode") for t in running())
        check("两栏能同时读（并行不被挡）",
              modes == ["map", "monsters"], "running=%r" % (modes,))
        check("两个按钮各自挂着「在读」小点",
              find_object("mapBusyDot") is not None
              and find_object("monBusyDot") is not None,
              "map=%r mon=%r" % (find_object("mapBusyDot"),
                                 find_object("monBusyDot")))
        check("记录区标题写着读着几条",
              any("读着 2 条" in t for t in texts_inside("taskSection")),
              "texts=%r" % (texts_inside("taskSection"),))
        next_step(250, step_cancel)

    # 取消：点地图那条的「取消」
    def step_cancel():
        target = None
        for row in find_all("taskRow"):
            if any("地图" in t for t in row_texts(row)):
                target = row
                break
        check("找得到地图那条记录", target is not None)
        cancel = None
        for item in find_all("taskCancel"):
            if item.parentItem() is not None and item.parentItem().parentItem() is target:
                cancel = item
        check("找得到它的「取消」", cancel is not None)
        click(cancel)
        # 任务表里可能有多条 mode=map（fixture 那条是 done）：看"有没有一条被取消了"
        map_states = [t.get("state") for t in controller.tasks
                      if t.get("mode") == "map"]
        check("点取消把那条标成已取消", "cancelled" in map_states,
              "map_states=%r" % (map_states,))
        check("取消之后地图栏按钮回到「读取」",
              texts_inside("readMap") == ["读取"],
              "labels=%r" % (texts_inside("readMap"),))
        next_step(250, step_retry)

    # 重试：把手册那条标成失败，点「重试」应该重新跑
    def step_retry():
        for task in controller._tasks:
            if task.get("mode") == "monsters":
                task["state"] = "failed"
                task["text"] = "读不到局面：读操作超时"
        controller.tasksChanged.emit()
        app.processEvents()
        # 记录在内容区最底下：先滚到底，否则小窗/裁切会把这一行挡掉，点了个空
        flick = find_object("contentFlick")
        max_y = max(0.0, float(flick.property("contentHeight"))
                    - float(flick.height()))
        flick.setProperty("contentY", max_y)
        app.processEvents()
        retry = find_object("taskRetry")
        check("失败那条显示「重试」", retry is not None,
              "texts=%r" % (texts_inside("taskSection"),))
        click(retry)
        failed = [t for t in controller.tasks if t.get("mode") == "monsters"][0]
        check("点重试重新开始跑", failed.get("state") == "running",
              "task=%r" % (failed,))
        # 收工（真读取要抓用户的窗口，自检里不跑）
        for task in controller._tasks:
            task["state"] = "done"
        controller._active = 0
        controller._reading = False
        controller.readingChanged.emit()
        controller.tasksChanged.emit()
        check("读完之后顶栏闪绿（读到新数据）",
              window.property("barFlash") == "ok",
              "barFlash=%r" % (window.property("barFlash"),))
        next_step(1100, verify_read_done)

    def verify_read_done():
        check("读取结束后两个按钮都回到「读取」",
              texts_inside("readMon") == ["读取"]
              and texts_inside("readMap") == ["读取"],
              "map=%r mon=%r" % (texts_inside("readMap"),
                                 texts_inside("readMon")))
        # 闪一下就该自己收回去（900ms），不能一直亮着
        check("那次绿闪会自己消失", window.property("barFlash") == "",
              "barFlash=%r" % (window.property("barFlash"),))
        check("记录里保留这次读到的结果",
              bool(find_all("taskRow")),
              "rows=%d" % len(find_all("taskRow")))
        next_step(150, step_refresh)

    # ---------------- 4.5 导航条的 ↻：只刷人物状态 ----------------
    def step_refresh():
        check("刷新状态之前不在刷新", controller.updating is False)
        click(find_object("statusRefresh"))
        check("点「↻」只刷人物状态（不读地图）",
              controller.updating is True and controller.reading is False,
              "updating=%r reading=%r" % (controller.updating,
                                          controller.reading))
        next_step(300, verify_refresh_done)

    def verify_refresh_done():
        check("刷新中图标变成「…」",
              any("…" in t for t in texts_inside("statusRefresh")),
              "labels=%r" % (texts_inside("statusRefresh"),))
        controller._updating = False
        controller.readingChanged.emit()
        next_step(300, verify_refresh_icon)

    def verify_refresh_icon():
        check("刷新结束图标回到「↻」",
              "↻" in " ".join(texts_inside("statusRefresh")),
              "labels=%r" % (texts_inside("statusRefresh"),))
        next_step(150, step_chat)

    # ---------------- 5. 对话：完整历史 + 输入发送 ----------------
    def step_chat():
        rows = find_all("chatRowItem")
        check("对话显示完整历史（fixture 两条都在）", len(rows) == 2,
              "rows=%d" % len(rows))
        check("对话有「你」和「AI」", find("你") != [] and find("AI") != [])
        # 完整历史 + 长回答折行（用户："我需要完整的历史"）
        long_text = ("地下 30 这一层还有血蚊 5 只（其中 2 只已经打过）、铁卫 1 只；"
                     "下去前记得先拿红血瓶，地下 29 已经清空，可以放心走。")
        controller._chat_log = [
            {"who": "你", "text": "第一问", "at": "14:20"},
            {"who": "AI", "text": "第一答", "at": "14:20"},
            {"who": "你", "text": "地下30还剩什么？", "at": "14:31"},
            {"who": "AI", "text": long_text, "at": "14:31"},
        ]
        controller.chatLogChanged.emit()
        app.processEvents()
        QTest.qWait(150)      # 窗口高度会跟着变：等布局跑完再量行数
        app.processEvents()
        rows = find_all("chatRowItem")
        check("四轮对话逐条都留着（不是只剩最后一问一答）", len(rows) == 4,
              "rows=%d" % len(rows))
        first_row = row_texts(rows[0]) if rows else []
        check("最上面还是最早那一句",
              any("第一问" in text for text in first_row),
              "first=%r" % (first_row,))
        says = find_all("chatText")
        check("长回答折行、不是一行截断",
              len(says) == 4
              and int(says[-1].property("lineCount")) >= 2
              and says[-1].height() > 20,
              "lines=%r h=%r"
              % (says[-1].property("lineCount") if says else None,
                 says[-1].height() if says else None))
        dock = find_object("chatBar")
        check("对话卡跟着内容长高", dock is not None and dock.height() > 80,
              "height=%r" % (dock.height() if dock else None,))
        # 历史很长：卡片封顶、内容在卡里滚，并且停在最新一句
        many = []
        for index in range(12):
            many.append({"who": "你", "text": "问题 %d" % index, "at": "14:40"})
            many.append({"who": "AI", "text": "回答 %d" % index, "at": "14:40"})
        controller._chat_log = many
        controller.chatLogChanged.emit()
        app.processEvents()
        QTest.qWait(150)
        app.processEvents()
        flick = find_object("chatFlick")
        check("历史长了在卡里滚（有上限）",
              flick is not None
              and flick.property("contentHeight") > flick.height(),
              "content=%r view=%r"
              % (flick.property("contentHeight") if flick else None,
                 flick.height() if flick else None))
        check("默认停在最新一句",
              flick is not None
              and abs(flick.property("contentY")
                      - (flick.property("contentHeight") - flick.height())) <= 2,
              "y=%r want=%r"
              % (flick.property("contentY") if flick else None,
                 (flick.property("contentHeight") - flick.height())
                 if flick else None))
        # 收工：留两条短消息，后面的步骤按这两条查
        controller._chat_log = [
            {"who": "你", "text": "第一问", "at": "14:20"},
            {"who": "AI", "text": "第一答", "at": "14:20"},
        ]
        controller.chatLogChanged.emit()
        app.processEvents()
        field = find_object("chatInput")
        check("找得到输入框", field is not None)
        field.setProperty("text", "红头怪还剩几只")
        app.processEvents()
        check("输入框能拿到文字", field.property("text") == "红头怪还剩几只",
              "text=%r" % (field.property("text"),))
        click(find_object("chatSend"))
        log = controller._chat_log
        check("点发送把话发出去", log and log[-1]["who"] == "你"
              and log[-1]["text"] == "红头怪还剩几只",
              "log=%r" % (log[-1] if log else None,))
        check("发完输入框清空", field.property("text") == "",
              "text=%r" % (field.property("text"),))
        next_step(200, step_chat_enter)

    def step_chat_enter():
        field = find_object("chatInput")
        click(field)
        check("点一下输入框能拿到焦点", field.hasActiveFocus(),
              "focus=%r" % (field.hasActiveFocus(),))
        type_ascii("hi")
        check("键盘能往输入框里打字", field.property("text") == "hi",
              "text=%r" % (field.property("text"),))
        press(Qt.Key_Return, "\r")
        log = controller._chat_log
        check("等回复时按回车不会叠着发（字也还在）",
              log and log[-1]["text"] == "红头怪还剩几只"
              and field.property("text") == "hi",
              "last=%r text=%r" % (log[-1] if log else None,
                                   field.property("text")))
        # 回复到了（自检里不跑真模型，手动把对话状态松开）
        controller._chatting = False
        controller.chattingChanged.emit()
        press(Qt.Key_Return, "\r")
        # _log 是"换一个新列表"（self._chat_log = ... + [entry]），要重新取
        log = controller._chat_log
        check("回车也能发", log and log[-1]["text"] == "hi",
              "last3=%r" % (log[-3:] if log else None,))
        check("回车发完输入框清空", field.property("text") == "",
              "text=%r" % (field.property("text"),))
        next_step(250, step_escape)

    def step_escape():
        click(find_object("chatInput"))
        press(Qt.Key_Escape)
        check("输入框里按 Esc 不会把程序退掉", window.isVisible())
        # 后面的 Esc 测试要能落到快捷键上：把焦点从输入框拿开
        find_object("chatInput").setProperty("focus", False)
        app.processEvents()
        next_step(150, step_collapse)

    # ---------------- 6. 折叠 / 展开 ----------------
    def step_collapse():
        bar = find_object("topBar")
        click(bar, 0.5, 0.5)
        check("点抬头收起", window.property("collapsed") is True,
              "collapsed=%r" % (window.property("collapsed"),))
        next_step(450, verify_collapsed)

    def verify_collapsed():
        # 收起后留三样：导航条（软件名 + ✕）、塔名、状态行（血量/钥匙）
        check("收起后窗口高度 = 导航条 + 抬头 + 状态行",
              abs(window.height() - 102) <= 2, "height=%.0f" % window.height())
        # 平台层也不许再把它顶大：minimumHeight 设大了 Windows 会把它卡成 120，
        # 界面上方一条、下面一片空白（用户："折叠后还是有一大片空白"）
        check("平台真的按 102 放下去了（没被最小高度卡住）",
              abs(window.geometry().height() - 102) <= 2,
              "geometry=%.0f" % window.geometry().height())
        check("收起后列表藏起来", find_object("contentFlick") is None)
        check("收起后对话也藏起来", find_object("chatBar") is None)
        check("收起后软件名还在（导航条）",
              any("拆塔辅助" in t for t in texts_inside("topBar")),
              "topBar=%r" % (texts_inside("topBar"),))
        check("收起后塔名还在", any("坐牢成仙" in t
                              for t in texts_inside("header")))
        check("收起后四色钥匙还在",
              find_object("keyChips") is not None)
        click(find_object("topBar"), 0.5, 0.5)
        next_step(450, verify_expanded)

    def verify_expanded():
        check("再点一下展开", window.property("collapsed") is False)
        check("展开后高度回到内容高度",
              abs(window.height() - content_height()) <= 2,
              "height=%.0f want=%.0f" % (window.height(), content_height()))
        next_step(150, step_floor_sheet)

    # ---------------- 7. 地图的子界面：这一层 ----------------
    def step_floor_sheet():
        # 地图块一行三个、y 一样，排序分不出先后：按块上的层名挑
        target = None
        for tile in find_all("mapTile"):
            if any("通天塔1" in t for t in row_texts(tile)):
                target = tile
                break
        check("找得到通天塔1 的地图块", target is not None)
        click(target)
        check("点地图块打开这一层的子界面",
              window.property("openFloor") == "通天塔1"
              and find_object("floorCard") is not None,
              "openFloor=%r card=%r" % (window.property("openFloor"),
                                        find_object("floorCard")))
        check("子界面里有这一层的怪",
              len(find_all("floorMonRow")) == 2,
              "rows=%d" % len(find_all("floorMonRow")))
        check("子界面里有这一层的资源",
              len(find_all("floorItemRow")) == 1,
              "rows=%d" % len(find_all("floorItemRow")))
        shot = find_object("floorShot")
        check("子界面里的地图截图整张显示",
              shot is not None and shot.property("source") != "",
              "source=%r" % (shot.property("source") if shot else None,))
        box = find_object("floorShotBox")
        check("截图区按比例撑高（不是中间一小条）",
              box is not None and box.height() >= 120,
              "box_h=%.0f" % (box.height() if box else 0))
        # 行里带缩略图（用户问"怪物的缩略图呢"）
        thumbs = find_all("floorMonThumb")
        images = [i for i in inside("floorMonThumb")
                  if i.metaObject().className().startswith("QQuickImage")
                  and shown(i)]
        check("本层的怪行有缩略图",
              len(thumbs) == 2 and len(images) >= 1,
              "thumbs=%d images=%d" % (len(thumbs), len(images)))
        next_step(250, verify_floor_toggle)

    def verify_floor_toggle():
        row = find_all("floorMonDone")[0]
        click(row)
        done_flags = [m.get("done") for m in controller._map_history[0]["mons"]]
        check("点圆点能把这只怪标成打过了", done_flags[0] is True,
              "done=%r" % (done_flags,))
        click(find_all("floorMonDone")[0])
        next_step(250, verify_floor_pick)

    def verify_floor_pick():
        click(find_object("floorAddMon"))
        app.processEvents()
        QTest.qWait(120)          # 下拉菜单要等排完版才量得到位置/高度
        app.processEvents()
        check("点「＋加怪」打开挑选层",
              window.property("pickMode") == "mon"
              and find_object("pickLayer") is not None,
              "pickMode=%r" % (window.property("pickMode"),))
        rows = find_all("pickRow")
        check("挑选层里有候选怪", len(rows) >= 2, "rows=%d" % len(rows))
        # 用户："地图下的加怪和加资源怎么不是下拉菜单"
        card = find_object("pickCard")
        button = find_object("floorAddMon")
        menu_ok = card is not None and button is not None and card.width() < 260
        if menu_ok:
            below = abs(scene_y(card) - (scene_y(button) + button.height())) < 40
            above = abs((scene_y(card) + card.height()) - scene_y(button)) < 40
            menu_ok = below or above
        check("加怪是挂在「＋」下面的下拉菜单（不是整页盖住）",
              menu_ok,
              "card=%r button=%r"
              % ((card.width(), card.height(), scene_y(card))
                 if card else None,
                 (button.height(), scene_y(button)) if button else None))
        before = len(controller._map_history[0]["mons"])
        click(rows[0])
        check("选一只就加进这一层",
              len(controller._map_history[0]["mons"]) == before + 1,
              "mons=%d" % len(controller._map_history[0]["mons"]))
        # 加资源同样是下拉菜单
        add_item = find_object("floorAddItem")
        click(add_item)
        app.processEvents()
        QTest.qWait(120)
        app.processEvents()
        card = find_object("pickCard")
        items = find_all("pickRow")
        near = False
        if card is not None and add_item is not None:
            below = abs(scene_y(card) - (scene_y(add_item) + add_item.height())) < 40
            above = abs((scene_y(card) + card.height()) - scene_y(add_item)) < 40
            near = below or above
        check("点「＋加资源」也是下拉菜单",
              window.property("pickMode") == "item"
              and card is not None and card.width() < 260
              and len(items) > 0 and near,
              "pickMode=%r card=%r rows=%d near=%r"
              % (window.property("pickMode"),
                 (card.width(), card.height()) if card else None, len(items),
                 near))
        item_before = len(controller._map_history[0]["items"])
        click(items[0])
        check("选一个资源就加进这一层",
              len(controller._map_history[0]["items"]) == item_before + 1,
              "items=%d" % len(controller._map_history[0]["items"]))
        next_step(250, verify_floor_preview)

    def verify_floor_preview():
        click(find_object("floorShot"))
        check("点子界面的截图能看大图",
              find_object("previewShot") is not None)
        press(Qt.Key_Escape)
        check("Esc 先关大图（不关子界面）",
              find_object("previewShot") is None
              and window.property("openFloor") != "",
              "openFloor=%r" % (window.property("openFloor"),))
        press(Qt.Key_Escape)
        check("再按 Esc 关子界面",
              window.property("openFloor") == ""
              and find_object("floorSheet") is None,
              "openFloor=%r" % (window.property("openFloor"),))
        next_step(200, step_floor_multi)

    # 小窗能多开、能拖、能放大（用户："怎么不能移动 / 怎么不能多开 / 怎么不能放大"）
    def child_of(root, name):
        stack = list(root.childItems())
        while stack:
            node = stack.pop()
            if node.objectName() == name:
                return node
            stack.extend(node.childItems())
        return None

    def floor_card(name):
        """按层名找卡片：拖完以后 y 变了，不能再用"第 0 个"认窗口。"""
        for card in find_all("floorCard"):
            title = child_of(card, "floorTitle")
            if title is not None and plain(title.property("text")) == name:
                return card
        return None

    def step_floor_multi():
        target = None
        for tile in find_all("mapTile"):
            if any("通天塔1" in t for t in row_texts(tile)):
                target = tile
        click(target)
        check("先开一扇", len(find_all("floorCard")) == 1,
              "cards=%d" % len(find_all("floorCard")))
        click(find_object("floorMore"))
        check("抬头的 ＋ 能再开一扇", len(find_all("floorCard")) == 2,
              "cards=%d" % len(find_all("floorCard")))
        card = floor_card("通天塔2")
        check("按层名找得到上面那扇", card is not None,
              "cards=%r" % ([row_texts(c)[:1] for c in find_all("floorCard")],))
        sheet = window_of(card)
        before = (sheet.x(), sheet.y())
        drag(child_of(card, "floorTitle"), 24, 40)
        sheet = window_of(floor_card("通天塔2"))
        after = (sheet.x(), sheet.y())
        check("拖抬头能把小窗挪走（真窗口）", after != before,
              "before=%r after=%r" % (before, after))
        # 拖到右边贴住、松手，再往回拖 24px：要立刻跟手（用户："拖动时一直在抖动"）
        drag(child_of(card, "floorTitle"), 4000, 0)
        sheet = window_of(floor_card("通天塔2"))
        screen = app.primaryScreen().geometry()
        edge = sheet.x()
        limit = screen.x() + screen.width() - sheet.width() - 2
        check("拖到屏幕边上会停住（能拖到软件窗口外面，但不会掉出屏幕）",
              abs(edge - limit) <= 2,
              "edge=%r limit=%r" % (edge, limit))
        check("小窗确实跑到了主窗口右边外面",
              edge + sheet.width() > window.x() + window.width(),
              "sheet.right=%r main.right=%r"
              % (edge + sheet.width(), window.x() + window.width()))
        drag(child_of(card, "floorTitle"), -24, 0)
        sheet = window_of(floor_card("通天塔2"))
        back = sheet.x()
        check("从边上往回拖立刻跟手（不是先还债再跳）",
              abs(back - (edge - 24)) <= 3,
              "edge=%r back=%r want=%r" % (edge, back, edge - 24))
        # 右下角拉大（用户："怎么不能放大"）
        size0 = (card.property("width"), card.property("height"))
        list0 = card.property("listMax")
        shot0 = child_of(card, "floorShot").property("paintedWidth")
        box0 = child_of(card, "floorShotBox").property("height")
        grip = child_of(card, "floorGrip")
        check("小窗右下角有拉大的手柄", grip is not None)
        # 拉得多一点：截图现在是**真地图裁出来的方图**（比方图前那张矮宽的整窗截图
        # 高），默认清单区已经顶到 150 的上限，只拉 30px 反而会把它压小。
        drag(grip, 60, 400)
        card = floor_card("通天塔2")
        size1 = (card.property("width"), card.property("height"))
        check("拖手柄能把小窗放大",
              size1[0] > size0[0] + 8 and size1[1] > size0[1] + 8,
              "size=%r -> %r" % (size0, size1))
        check("放大后清单可以占更高",
              card.property("listMax") > list0,
              "listMax=%r -> %r" % (list0, card.property("listMax")))
        # 用户："放大地图的小窗的时候地图不会一起变大"
        shot1 = child_of(card, "floorShot").property("paintedWidth")
        box1 = child_of(card, "floorShotBox").property("height")
        check("地图跟着小窗一起变大",
              shot1 > shot0 + 4 and box1 > box0,
              "地图宽 %r -> %r，截图区高 %r -> %r"
              % (shot0, shot1, box0, box1))
        press(Qt.Key_Escape)
        check("Esc 关最上面那扇（还剩一扇）",
              len(find_all("floorCard")) == 1,
              "cards=%d" % len(find_all("floorCard")))
        press(Qt.Key_Escape)
        check("再按一次全关掉", len(find_all("floorCard")) == 0,
              "cards=%d" % len(find_all("floorCard")))
        next_step(200, step_floor_refresh)

    # 地图块右上角的 ↻：重数这一层的怪和资源
    def step_floor_refresh():
        refresh = find_all("mapRefresh")
        check("每个地图块都有刷新按钮", len(refresh) >= 1,
              "buttons=%d" % len(refresh))
        before = len(controller.tasks)
        click(refresh[0])
        check("点 ↻ 排了一条\"读这层地图\"的任务",
              len(controller.tasks) == before + 1
              and any("的地图" in str(t.get("text") or "")
                      for t in controller.tasks),
              "tasks=%r" % ([t.get("text") for t in controller.tasks],))
        check("正在数的层写在 countingFloor 上",
              controller.countingFloor != "",
              "countingFloor=%r" % (controller.countingFloor,))
        check("点 ↻ 没顺带打开这一层的小窗",
              window.property("openFloor") == "")
        # 收工：把"正在数"清掉，不影响后面的检查
        controller._counting_floor = ""
        controller.countingChanged.emit()
        for task in controller._tasks:
            if task.get("state") == "running":
                task["state"] = "done"
        controller.tasksChanged.emit()
        next_step(200, step_monster_editor)

    # ---------------- 7.5 怪物编辑界面 ----------------
    def step_monster_editor():
        target = None
        for row in find_all("monRow"):
            if any("红头怪" in t for t in row_texts(row)):
                target = row
                break
        check("找得到带手册记录的那一行（红头怪）", target is not None)
        click(target)
        check("点怪物行打开编辑界面",
              window.property("monEdit") >= 0
              and find_object("monEditCard") is not None,
              "monEdit=%r" % (window.property("monEdit"),))
        check("编辑界面有缩略图",
              find_object("monEditIcon") is not None)
        # 名字在抬头里直接改（不再单占一行、也不和标题重复）
        name_field = find_object("monNameField")
        check("名字在抬头里就能改",
              name_field is not None
              and name_field.property("text") == "红头怪",
              "name=%r" % (name_field.property("text") if name_field else None,))
        # 数值：生命/攻击/防御 一行，金币/经验 一行（用户指定的排法）
        hp_box = find_object("monHpField")
        atk_box = find_object("monAtkField")
        def_box = find_object("monDefField")
        gold_box = find_object("monGoldField")
        exp_box = find_object("monExpField")
        first = [b for b in (hp_box, atk_box, def_box) if b is not None]
        check("生命/攻击/防御 在同一行",
              len(first) == 3
              and max(scene_y(b) for b in first)
              - min(scene_y(b) for b in first) <= 2,
              "ys=%r" % ([round(scene_y(b)) for b in first],))
        check("金币/经验 在下一行",
              gold_box is not None and exp_box is not None
              and abs(scene_y(gold_box) - scene_y(exp_box)) <= 2
              and scene_y(gold_box) > scene_y(hp_box) + 10,
              "gold_y=%.0f exp_y=%.0f hp_y=%.0f"
              % (scene_y(gold_box), scene_y(exp_box), scene_y(hp_box)))
        check("三格真的横着排开（x 递增）",
              hp_box is not None and atk_box is not None and def_box is not None
              and scene_x(hp_box) < scene_x(atk_box) < scene_x(def_box),
              "x=%r" % ([round(scene_x(b)) for b in first],))
        check("编辑界面带出原来的金币",
              gold_box is not None and gold_box.property("text") == "12",
              "gold=%r" % (gold_box.property("text") if gold_box else None,))
        # 技能：名称 + 技能介绍（原来的"数值"删掉了）
        name_cell = find_object("monSkillName")
        effect_cell = find_object("monSkillEffect")
        check("技能行是「名称 + 介绍」两格",
              name_cell is not None and effect_cell is not None
              and find_object("monSkillValue") is None)
        check("手册技能的介绍从手册带出来",
              effect_cell is not None
              and "首先攻击" in str(effect_cell.property("text") or ""),
              "effect=%r" % (effect_cell.property("text") if effect_cell else None,))
        check("手册技能的名称是只读的",
              name_cell is not None
              and bool(name_cell.property("readOnly")),
              "readOnly=%r" % (name_cell.property("readOnly")
                               if name_cell else None,))
        # 用户："图标 点头像换图一行都删掉"
        labels = [plain(i.property("text")) for i in walk()
                  if is_text(i) and shown(i)]
        check("「图标 / 点头像换图 / 清空」那一行删掉了",
              find_object("monIconClear") is None
              and "图标" not in labels and "点头像换图" not in labels,
              "labels=%r" % ([x for x in labels if "图标" in x or "换图" in x],))
        # 用户："只有一行的和有多行的要有不同的显示方式"
        row = find_object("monSkillRow")
        check("单行技能就摆一行（不撑成块）",
              row is not None and not bool(row.property("multi")),
              "multi=%r" % (row.property("multi") if row else None,))
        # ---- 头像就是换图按钮（用户："点击头像修改图标"） ----
        avatar = find_object("monIconPick")
        check("头像本身可以点（换图不用另找按钮）",
              avatar is not None
              and not any("从素材库选" == t for t in
                          [plain(i.property("text")) for i in walk()
                           if is_text(i) and shown(i)]))
        click(avatar)
        cells = find_all("iconCell")
        sources = [item.property("source") for item in find_all("iconCellImage")]
        check("点头像打开选图界面", find_object("iconCard") is not None,
              "cells=%d" % len(cells))
        check("选图界面没有重复的图",
              len(sources) == len(set(sources)),
              "cells=%d unique=%d" % (len(sources), len(set(sources))))
        check("选图张数 = 去重后的素材数",
              len(cells) == len(controller.monsterIconChoices()),
              "cells=%d choices=%d"
              % (len(cells), len(controller.monsterIconChoices())))
        # ---- 素材库：只摆图 + 种族标题 + 搜索（用户："单个怪不要名字"） ----
        def matching(word):
            """素材库的搜索规则：名字 / id / 并掉的别名，含这个词就算命中。"""
            word = word.strip().lower()
            return [row for row in controller.monsterIconChoices()
                    if any(word in str(text).lower() for text in
                           [row["name"], row["id"]]
                           + list(row.get("aliases") or []))]

        check("格子上不写名字，只有图", not find_all("iconCellName"),
              "names=%d" % len(find_all("iconCellName")))
        headers = [plain(item.property("text"))
                   for item in find_all("iconGroupName")]
        check("每个种族都有标题（标题里有名字）",
              len(headers) == len(controller.monsterIconGroups())
              and any("史莱姆" in head for head in headers),
              "headers=%r" % (headers[:8],))
        # 照 QQ：搜索框挂在"搜索"页签里，点了才出现
        click(find_object("iconTabSearch"))
        app.processEvents()
        query = find_object("iconSearch")
        check("点「搜索」页签才出现搜索框", query is not None)
        query.setProperty("text", "史莱姆")
        app.processEvents()
        filtered = find_all("iconCell")
        kept = [row["name"] for row in matching("史莱姆")]
        check("搜索按名字过滤",
              0 < len(filtered) < len(cells) and len(filtered) == len(kept)
              and all("史莱姆" in str(name) for name in kept),
              "cells=%d filtered=%d kept=%r"
              % (len(cells), len(filtered), kept[:6]))
        count_text = plain(find_object("iconCount").property("text"))
        check("搜索时角标写着命中/总数",
              "/" in count_text, "count=%r" % (count_text,))
        # 两座塔各存一份的图并成一张后，改名前/另一座塔的名字也要搜得到
        # （046 石头怪 = xinxin2_rock 并掉了 xinxin_rock；旧名「石怪」还在 names 里）
        query.setProperty("text", "石怪")
        app.processEvents()
        alias_hits = [row["name"] for row in matching("石怪")]
        check("并掉/改名的旧名字还能搜到（石怪 → 石头怪）",
              alias_hits == ["石头怪"],
              "hits=%r" % (alias_hits,))
        # 真按键输入（不是只改属性）：编号也能搜
        query.setProperty("text", "")
        app.processEvents()
        click(query)
        app.processEvents()
        type_ascii("E33")
        app.processEvents()
        check("搜索框能真的打字",
              plain(window.property("iconQuery")).lower() == "e33",
              "query=%r" % (window.property("iconQuery"),))
        typed = find_all("iconCell")
        check("按编号也能搜到",
              0 < len(typed) < len(cells), "cells=%d" % (len(typed),))
        query.setProperty("text", "史莱姆")
        app.processEvents()
        filtered = find_all("iconCell")
        click(filtered[0])
        app.processEvents()
        check("点搜索结果就选中这张图",
              window.property("monIconId") != ""
              and window.property("iconPicker") is False
              and find_object("iconPicker") is None,
              "id=%r" % (window.property("monIconId"),))
        # 再开一次：搜索框要清空；Esc 关掉选图、编辑框还在
        click(find_object("monIconPick"))
        app.processEvents()
        click(find_object("iconTabSearch"))
        app.processEvents()
        check("重开选图时搜索框是空的",
              plain(find_object("iconSearch").property("text")) == ""
              and len(find_all("iconCell")) == len(cells),
              "text=%r cells=%d"
              % (plain(find_object("iconSearch").property("text")),
                 len(find_all("iconCell"))))
        press(Qt.Key_Escape)
        check("Esc 关掉选图界面（编辑框还在）",
              find_object("iconPicker") is None
              and window.property("monEdit") >= 0,
              "monEdit=%r" % (window.property("monEdit"),))
        # ---- 加技能只有一个按钮 + 下拉菜单 ----
        labels = [plain(i.property("text")) for i in walk()
                  if is_text(i) and shown(i)]
        check("加技能只剩一个按钮",
              find_object("monSkillPick") is not None
              and find_object("monSkillAdd") is None
              and "从手册选" not in labels,
              "labels=%r" % ([x for x in labels if "技能" in x or "选" in x],))
        check("Esc 关掉选图后技能行还在",
              find_object("monSkillName") is not None)
        button = find_object("monSkillPick")
        click(button)
        app.processEvents()
        menu = find_object("skillCard")
        custom = find_object("skillPickCustom")
        check("点「＋ 加技能」弹出下拉菜单",
              menu is not None and custom is not None,
              "rows=%d" % len(find_all("skillPickRow")))
        check("下拉里第一项是「自定义」",
              custom is not None
              and any("自定义" in t for t in row_texts(custom)))
        check("下拉里列出了手册的技能",
              len(find_all("skillPickRow")) == len(controller.skillCatalog),
              "rows=%d catalog=%d" % (len(find_all("skillPickRow")),
                                      len(controller.skillCatalog)))
        check("下拉菜单挂在按钮下面（不是居中卡片）",
              menu is not None and button is not None
              and menu.mapToScene(QPointF(0, 0)).y()
              >= button.mapToScene(QPointF(0, 0)).y() - 1,
              "menu_y=%.0f btn_y=%.0f"
              % (menu.mapToScene(QPointF(0, 0)).y(),
                 button.mapToScene(QPointF(0, 0)).y()))
        # 选「自定义」= 原来那个「＋ 加」空行
        click(custom)
        app.processEvents()
        check("选「自定义」加了一行空技能",
              len(mon_skills()) == 2
              and find_object("skillCard") is None,
              "skills=%r" % (mon_skills(),))
        names_now = find_all("monSkillName")
        check("自定义那行的名称可以改（其余不能）",
              len(names_now) == 2
              and bool(names_now[0].property("readOnly"))
              and not bool(names_now[1].property("readOnly")),
              "readOnly=%r" % ([n.property("readOnly") for n in names_now],))
        # 用户："自定义怎么只能写技能名称不能写技能介绍"
        edit = find_object("monSkillEffectEdit")
        check("自定义技能能写介绍", edit is not None)
        if edit is not None:
            edit.setProperty("text", "每两回合召唤一只小怪")
            app.processEvents()
            skills_now = mon_skills()
            check("写的介绍记在技能上",
                  bool(skills_now)
                  and str((skills_now[-1] or {}).get("effect") or "")
                  == "每两回合召唤一只小怪",
                  "skills=%r" % (skills_now,))
            check("自定义技能那一行换成多行块",
                  len(find_all("monSkillRow")) == 2
                  and bool(find_all("monSkillRow")[-1].property("multi")),
                  "multi=%r" % ([r.property("multi")
                                 for r in find_all("monSkillRow")],))
        # 全删掉：只剩一句提示（列头已经没有这一行了）
        window.removeSkill(1)
        window.removeSkill(0)
        app.processEvents()
        check("没有技能时只剩一句提示",
              find_object("monSkillRow") is None
              and find_object("monSkillName") is None,
              "rows=%r" % (find_all("monSkillRow"),))
        check("没有技能时给一句提示",
              any("＋ 加技能" in t for t in
                  [plain(i.property("text")) for i in walk()
                   if is_text(i) and shown(i)]))
        # 再从下拉里挑一个有数值参数的技能（破甲：防御百分比）
        click(find_object("monSkillPick"))
        app.processEvents()
        rows = find_all("skillPickRow")
        check("下拉里能选到手册技能", len(rows) > 0, "rows=%d" % len(rows))
        target = next((row for row in rows
                       if any("破甲" == t for t in row_texts(row))), None)
        check("下拉里能找到破甲", target is not None)
        click(target)
        app.processEvents()
        picked = [str((row or {}).get("name") or "")
                  for row in mon_skills()]
        check("选中的技能进了技能表",
              len(picked) == 1 and picked[0] == "破甲",
              "skills=%r" % (picked,))
        # 介绍是只读的手册原话；数字单独一格（算伤害用的参数）
        effect_cell = find_object("monSkillEffect")
        check("手册技能的介绍显示出来",
              effect_cell is not None
              and "防御" in str(effect_cell.property("text") or ""),
              "effect=%r" % (effect_cell.property("text") if effect_cell else None,))
        params = find_all("monSkillParam")
        check("破甲有一个参数格", len(params) == 1, "cells=%d" % len(params))
        check("有参数的技能换成多行块",
              any(bool(r.property("multi")) for r in find_all("monSkillRow")),
              "multi=%r" % ([r.property("multi")
                             for r in find_all("monSkillRow")],))
        cell = find_object("monSkillParams")
        labels = row_texts(cell) if cell is not None else []
        check("参数格写着「防御百分比」和单位 %",
              any("防御百分比" in t for t in labels) and "%" in labels,
              "labels=%r" % (labels,))
        check("参数一开始是空的",
              len(params) == 1 and params[0].property("text") == "",
              "value=%r" % (params[0].property("text") if params else None,))
        params[0].setProperty("text", "50")
        app.processEvents()
        field = find_object("monHpField")
        check("编辑界面带出原来的生命值",
              field is not None and field.property("text") == "80",
              "hp=%r" % (field.property("text") if field else None,))
        field.setProperty("text", "8888")
        gold_box.setProperty("text", "34")
        app.processEvents()
        click(find_object("monSave"))
        check("改完点保存真的存进去",
              controller._monsters[0]["hp"] == "8888",
              "hp=%r" % (controller._monsters[0].get("hp"),))
        check("金币也跟着存进去了",
              controller._monsters[0].get("gold") == "34",
              "gold=%r" % (controller._monsters[0].get("gold"),))
        items = controller._monsters[0].get("skill_items") or [{}]
        first = items[0] or {}
        check("技能参数按字段存下来了",
              (first.get("params") or {}) == {"defValue": "50"},
              "params=%r" % (first.get("params"),))
        check("技能存了引擎 code（算伤害的键）",
              str(first.get("code") or "") == "7",
              "code=%r" % (first.get("code"),))
        check("保存后编辑界面关掉", window.property("monEdit") == -1)
        next_step(300, step_battle)

    # ---------------- 7.5 伤害计算（真窗口 + 问号菜单） ----------------
    def step_battle():
        entry = find_object("battleOpen")
        check("导航条上有伤害计算入口 ⚔", entry is not None)
        if entry is None:
            next_step(150, step_scroll)
            return
        click(entry)
        app.processEvents()
        battle = window.property("battleWindow")
        battle = battle.toQObject() if hasattr(battle, "toQObject") else battle
        check("⚔ 打开一扇独立窗口", battle is not None and battle is not window,
              "battle=%r" % (battle,))
        if battle is None:
            next_step(150, step_scroll)
            return
        check("人物数值从状态行带出来",
              find_object("battleHero_atkField") is not None
              and plain(find_object("battleHero_atkField").property("text")) != "",
              "atk=%r" % (plain(find_object("battleHero_atkField").property("text"))
                          if find_object("battleHero_atkField") else None,))
        # 用户："一行！！！" + "开头是一个勇者加箭头指向问号"
        rows = find_all("battleRow")
        check("打开就摆一行", len(rows) == 1, "rows=%d" % len(rows))
        check("行首是勇者", find_object("battleRowHero") is not None)
        ask = find_object("battleRowAsk")
        check("链尾有个问号", ask is not None and ask.isVisible(),
              "ask=%r" % (ask,))
        # 点问号 → 菜单里怪和资源一个列表（用户："点问号选怪或资源"）
        if ask is not None:
            click(ask)
        app.processEvents()
        QTest.qWait(120)          # 菜单要排完版才量得到行
        app.processEvents()
        picks = find_all("battlePickRow")
        texts = " ".join(" ".join(row_texts(row)) for row in picks)
        check("点问号列出手册里的怪和资源", len(picks) > 0, "rows=%d" % len(picks))
        # 菜单分两个标签页（用户："应该只有两个标签页分别是怪物和资源（包含 4 色宝石）"）
        tab = find_object("battleTabItem")
        check("菜单有「资源」标签页", tab is not None)
        if tab is not None:
            click(tab)
            app.processEvents()
            QTest.qWait(120)
            texts_item = " ".join(" ".join(row_texts(row))
                                  for row in find_all("battlePickRow"))
            check("「资源」页里有 4 色宝石",
                  all(gem in texts_item
                      for gem in ("红宝石", "蓝宝石", "绿宝石", "黄宝石")),
                  "texts=%r" % (texts_item[:80],))
            back = find_object("battleTabMonster")
            if back is not None:
                click(back)
                app.processEvents()
                QTest.qWait(120)
        picks = find_all("battlePickRow")
        if picks:
            click(picks[0])
            app.processEvents()
        plans = window.property("battlePlans")
        plans = plans.toVariant() if hasattr(plans, "toVariant") else plans
        steps = [step for step in (plans or [{}])[0].get("steps") or []]
        check("选完就接在这一行的链上", len(steps) == 1, "steps=%r" % (steps,))
        # 用户："计算按钮要在每一条后面"（以前钉在右边那一列）
        ask = find_object("battleRowAsk")
        run = find_object("battlePlanRun")
        check("「计算」跟在这一行链尾（问号后面）",
              ask is not None and run is not None
              and run.parentItem() is ask.parentItem(),
              "ask=%r run=%r" % (ask, run))
        # 用户："点计算后出结果" —— 选完还没算
        damage = find_object("battleRowDamage")
        check("没点计算前是一个破折号", plain(damage.property("text")) in ("", "—")
              if damage else False,
              "damage=%r" % (plain(damage.property("text")) if damage else None,))
        click(find_object("battlePlanRun"))
        app.processEvents()
        damage = find_object("battleRowDamage")
        text = plain(damage.property("text")) if damage else ""
        check("点「计算」后怪的后面写了掉多少血（带括号）",
              text.startswith("（−") and text.endswith("）"),
              "damage=%r" % (text,))
        total = find_object("battlePlanDamage")
        check("这一行右边有总掉血",
              total is not None and "总掉血" in plain(total.property("text")),
              "total=%r" % (plain(total.property("text")) if total else None,))
        # 改人物攻击 → 结果作废，再点一次「计算」才更新
        field = find_object("battleHero_atkField")
        before = text
        if field is not None:
            field.setProperty("text", "9999")
            app.processEvents()
            waiting = plain(find_object("battleRowDamage").property("text")) \
                if find_object("battleRowDamage") else ""
            check("改了数值结果先作废", waiting == "—", "damage=%r" % (waiting,))
            click(find_object("battlePlanRun"))
            app.processEvents()
            after = plain(find_object("battleRowDamage").property("text")) \
                if find_object("battleRowDamage") else ""
            check("再点「计算」掉血跟着变", after != before,
                  "%r -> %r" % (before, after))
        # 用户："伤害计算界面怎么不能拉伸窗口，怪物和资源得缩略图太大了，
        #      箭头太丑了，而且不明显，伤害外面要加括号，血攻防魔防怎么不像
        #      状态一样显示"
        grips = ("battleGripTL", "battleGripTR", "battleGripBL", "battleGrip",
                 "battleGripT", "battleGripB", "battleGripL", "battleGripR")
        check("四条边 + 四个角都能拉窗口",
              [name for name in grips if find_object(name) is None] == [],
              "缺=%r" % [name for name in grips if find_object(name) is None])
        icon = find_object("battleRowIcon")
        check("缩略图是 14（以前的 20 太大）",
              icon is not None and round(icon.width()) == 14,
              "w=%r" % (icon.width() if icon else None,))
        check("箭头是画出来的（两条斜线拼的 >）",
              len(find_all("chainArrowLeg")) >= 2,
              "legs=%d" % len(find_all("chainArrowLeg")))
        hp = find_object("battleHero_hpField")
        check("人物数值挨着图标（和状态行一个写法）",
              hp is not None and hp.width() <= 60,
              "w=%r" % (hp.width() if hp else None,))
        # 用户："点箭头要能插入"
        arrows = find_all("battleRowArrow")
        check("链上每一步前面都有个能点的箭头", len(arrows) >= 1,
              "arrows=%d" % len(arrows))
        if arrows:
            click(arrows[0])
            app.processEvents()
            QTest.qWait(120)
            app.processEvents()
            picks = find_all("battlePickRow")
            if picks:
                click(picks[0])
                app.processEvents()
            plans = window.property("battlePlans")
            plans = plans.toVariant() if hasattr(plans, "toVariant") else plans
            steps = [step for step in (plans or [{}])[0].get("steps") or []]
            check("点箭头选的东西插在最前面（不是接在最后）",
                  len(steps) == 2, "steps=%r" % (steps,))
        # 用户："每一条要能单独计算" —— 换顺序再算一次，底下写差别
        click(find_object("battleAddRow"))
        app.processEvents()
        asks = find_all("battleRowAsk")
        if len(asks) > 1:
            click(asks[1])
            app.processEvents()
            QTest.qWait(120)
            app.processEvents()
            picks = find_all("battlePickRow")
            if picks:
                click(picks[0])
                app.processEvents()
        runs = find_all("battlePlanRun")
        check("每行链尾都有自己的「计算」", len(runs) == 2, "runs=%d" % len(runs))
        if len(runs) > 1:
            click(runs[1])            # 只算第 2 行
            app.processEvents()
            QTest.qWait(80)
            app.processEvents()
            left = find_all("battlePlanRun")
            check("单独算完一行，另一行还是「计算」", len(left) == 1,
                  "runs=%d" % len(left))
        plans = window.property("battlePlans")
        plans = plans.toVariant() if hasattr(plans, "toVariant") else plans
        for i in range(len(plans or [])):
            window.battleComputePlan(i)          # 界面上没"全算"按钮了，逐行算
        app.processEvents()
        QTest.qWait(80)
        app.processEvents()
        totals = [plain(item.property("text"))
                  for item in find_all("battlePlanDamage")]
        check("两行各有自己的总掉血", len(totals) >= 2,
              "totals=%r" % (totals,))
        # 底栏的大黄块删了：最省的一行靠 ✓ 标记（battlePlanDamage 里带 ✔）
        best = [t for t in totals if "✔" in t]
        check("掉血最少的那一行打勾", len(best) == 1, "totals=%r" % (totals,))
        click(find_object("battleClear"))
        app.processEvents()
        check("清空之后一行都不剩", len(find_all("battleRow")) == 0)
        # 用户："点图标后修改怪物或资源的数值"
        click(find_object("battleAddRow"))
        app.processEvents()
        asks = find_all("battleRowAsk")
        if asks:
            click(asks[0])
            app.processEvents()
            QTest.qWait(120)
            app.processEvents()
            picks = find_all("battlePickRow")
            if picks:
                click(picks[0])
                app.processEvents()
        icons = find_all("battleRowIcon")
        check("链上每一步都有缩略图", len(icons) >= 1, "icons=%d" % len(icons))
        if icons:
            click(icons[0])
            app.processEvents()
            check("点缩略图打开参数编辑",
                  window.property("battleEditLayer") is True
                  and find_object("battleEditCard") is not None,
                  "layer=%r" % (window.property("battleEditLayer"),))
            check("参数编辑里有数量/血量/攻击",
                  find_object("battleEditCount") is not None
                  and find_object("battleEdithp") is not None
                  and find_object("battleEditatk") is not None,
                  "count=%r hp=%r" % (find_object("battleEditCount"),
                                      find_object("battleEdithp")))
            click(find_object("battleEditDone"))
            app.processEvents()
        click(find_object("battleClose"))
        app.processEvents()
        check("点 ✕ 关掉计算器（主窗口还在）",
              window.property("battleWindow") is None
              or (window.property("battleWindow").toQObject()
                  if hasattr(window.property("battleWindow"), "toQObject")
                  else None) is None)
        next_step(200, step_scroll)

    # ---------------- 8. 内容变多 → 可以滚 ----------------
    def step_scroll():
        flick = find_object("contentFlick")
        check("内容区是可滚动的", flick is not None)
        extra = [{"floor": "通天塔%d" % n, "url": thumb_url,
                  "mons": [{"name": "红头怪", "count": 1}], "items": []}
                 for n in range(3, 11)]
        controller._map_history = controller._map_history + extra
        controller.mapHistoryChanged.emit()
        app.processEvents()
        next_step(300, verify_scroll)

    def verify_scroll():
        flick = find_object("contentFlick")
        content = float(flick.property("contentHeight"))
        view = float(flick.height())
        check("层数变多后内容比窗口高", content > view,
              "content=%.0f view=%.0f" % (content, view))
        step = min(40.0, max(4.0, (content - view) / 2.0))
        flick.setProperty("contentY", step)
        app.processEvents()
        check("能往下滚", abs(float(flick.property("contentY")) - step) < 1,
              "contentY=%r want=%.0f" % (flick.property("contentY"), step))
        check("窗口高度有上限（不会顶穿屏幕）",
              window.height() <= 760, "height=%.0f" % window.height())
        next_step(150, finish)

    def finish():
        done()

    # 看门狗：某一步抛异常时检查链会断，事件循环空转看起来像"卡死"
    def watchdog():
        if STATE.get("code") is None:
            check("自检在 120 秒内跑完", False, "检查链断在中间（看日志最后一条）")
            done()

    QTimer.singleShot(120000, watchdog)
    next_step(400, step_structure)
    app.exec()
    return STATE.get("code", 1)


if __name__ == "__main__":
    raise SystemExit(main())
