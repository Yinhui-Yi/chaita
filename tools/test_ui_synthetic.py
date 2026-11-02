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
        from chaita.ui.controller.monsters import drag as monsters_mod

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
        # 导航条（工具图标）和状态卡（数值 + 钥匙）分开：用户嫌"血量钥匙"位置不合理
        nav = texts_inside("topBar")
        check("导航条上有五个工具图标和「置顶」",
              all(x in nav for x in ("↻", "＋", "⚔", "⇄", "✕", "置顶")),
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

        def inside(box, item):
            """item 是不是 box 的子孙。"""
            node = item
            while node is not None:
                if node is box:
                    return True
                node = node.parentItem()
            return False

        map_btn = find_object("readMap")
        mon_btn = find_object("readMon")
        dock = find_object("chatBar")
        check("地图栏和怪物栏各有一个「读取」",
              map_btn is not None and mon_btn is not None)
        if map_btn is not None and mon_btn is not None and dock is not None:
            # 窗口矮、内容在里面滚，按钮的屏幕位置会跑到对话卡下面去，所以不比 y，
            # 比"是不是在对话卡里面"（用户："不要放在对话框里"）
            check("两个「读取」都不在对话卡里，地图那个在怪物那个上方",
                  not inside(dock, map_btn) and not inside(dock, mon_btn)
                  and scene_y(map_btn) < scene_y(mon_btn),
                  "map=%.0f mon=%.0f dock=%.0f"
                  % (scene_y(map_btn), scene_y(mon_btn), scene_y(dock)))

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
        # 窗口矮、地图展开时怪物行/读取按钮会被滚到屏幕外（合成点击点不到）：
        # 先把地图和路线卡折起来，后面的怪物/技能/读取各步才点得到
        window.setProperty("mapCollapsed", True)
        window.setProperty("routeCollapsed", True)
        app.processEvents()
        rows = find_all("monRow")
        check("怪物一行一个（手册读到的 + 地图上有的）", len(rows) == 4,
              "rows=%d" % len(rows))
        names = [text for row in rows for text in row_texts(row)]
        check("手册里读到、地图上还没记的怪也列出来", "手册怪" in names,
              "texts=%r" % (names,))
        joined = " ".join(" ".join(row_texts(row)) for row in rows)
        check("怪物行有「剩 N」", "剩 4" in joined and "剩 2" in joined,
              "text=%r" % (joined,))
        # 用户："只要显示剩几只，不要别的"：列表里不再有生命/攻防、技能、总数
        check("怪物行只有名字和「剩 N」（没有生命/攻/防、×N、技能）",
              not any(x in joined for x in ("生命", "攻 ", "防 ", "×", "/")),
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
        # 手册怪是最后一行：窗口矮，先把内容区滚到底再点
        flick = find_object("contentFlick")
        if flick is not None:
            flick.setProperty("contentY", max(0.0, float(flick.property("contentHeight"))
                                              - float(flick.height())))
            app.processEvents()
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

    # ---------------- 3. 技能：一排胶囊、不列怪名 ----------------
    def step_skills():
        rows = find_all("skillRow")
        check("技能一颗胶囊一个", len(rows) == 2, "rows=%d" % len(rows))
        first = row_texts(rows[0]) if rows else []
        count_texts = [t for t in first if "/" in t]
        name_texts = [t for t in first if t and t not in count_texts]
        check("技能胶囊只有「名字 + 剩余/总数」",
              len(count_texts) == 1 and len(name_texts) == 1,
              "row=%r" % (first,))
        check("技能胶囊不列带这个技能的怪名",
              not any("头怪" in text or "骷髅" in text for text in first),
              "row=%r" % (first,))
        join = " ".join(" ".join(row_texts(row)) for row in rows)
        check("带某技能的怪还剩多少只写得出来",
              "3/5" in join and "1/1" in join,
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
        # 记录在内容区最底下：先滚到底，否则窗口矮时那一行在屏幕外，点了个空
        flick = find_object("contentFlick")
        flick.setProperty("contentY", max(0.0, float(flick.property("contentHeight"))
                                          - float(flick.height())))
        app.processEvents()
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
        # 对话是气泡：你说的靠右、AI 说的靠左
        says_now = sorted(find_all("chatText"), key=lambda i: scene_y(i))
        check("对话是气泡：你靠右、AI 靠左",
              len(says_now) == 2
              and says_now[0].mapToScene(QPointF(0, 0)).x()
              > says_now[1].mapToScene(QPointF(0, 0)).x(),
              "x=%r" % ([round(i.mapToScene(QPointF(0, 0)).x()) for i in says_now],))
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
        # 点导航条的空白处（中间现在是「置顶」按钮，点偏左一点才是空白）
        click(bar, 0.3, 0.5)
        check("点导航条空白处收起", window.property("collapsed") is True,
              "collapsed=%r" % (window.property("collapsed"),))
        next_step(450, verify_collapsed)

    def verify_collapsed():
        # 收起后留两样：导航条（工具图标）和状态卡（塔名 + 血量/钥匙）
        want = float(window.property("collapseChrome"))
        check("收起后窗口高度 = 导航条 + 状态卡（含上下留白）",
              abs(window.height() - want) <= 2,
              "height=%.0f want=%.0f" % (window.height(), want))
        # 平台层也不许再把它顶大：minimumHeight 设大了 Windows 会把它卡成 120，
        # 界面上方一条、下面一片空白（用户："折叠后还是有一大片空白"）
        check("平台真的按这个高度放下去了（没被最小高度卡住）",
              abs(window.geometry().height() - want) <= 2,
              "geometry=%.0f want=%.0f" % (window.geometry().height(), want))
        check("收起后列表藏起来", find_object("contentFlick") is None)
        check("收起后对话也藏起来", find_object("chatBar") is None)
        check("收起后导航条的工具图标还在",
              all(x in texts_inside("topBar") for x in ("↻", "＋", "⚔", "⇄", "✕")),
              "topBar=%r" % (texts_inside("topBar"),))
        check("收起后塔名还在", any("坐牢成仙" in t
                              for t in texts_inside("header")))
        check("收起后四色钥匙还在",
              find_object("keyChips") is not None)
        click(find_object("topBar"), 0.3, 0.5)
        next_step(450, verify_expanded)

    def verify_expanded():
        check("再点一下展开", window.property("collapsed") is False)
        check("展开后高度回到内容高度",
              abs(window.height() - content_height()) <= 2,
              "height=%.0f want=%.0f" % (window.height(), content_height()))
        # 这一层 / 怪物编辑 / 伤害计算三个子窗口由 tests/integration 的真点击测试覆盖
        next_step(150, step_scroll)

    # ---------------- 7. 内容变多 → 可以滚 ----------------
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
