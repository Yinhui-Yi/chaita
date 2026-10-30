"""用假数据把悬浮层（v12「塔级总览」）渲染成图片，用来检查布局。

用法：
    python tools/preview_overlay.py [输出png] [忽略：窗口高] [场景]

场景（都在下面 SCENARIOS 里）：
    default   正常一盘数据（两层地图 + 四种怪 + 两个技能 + 两行对话）
    empty     什么都没读过
    long      层数/怪物多到要滚动
    reading   正在读取（读取按钮变「读取中」）
    error     上一次读取失败（地图下面一行红字）
    collapsed 折叠成一条 48 高的抬头

为什么需要它：地图、怪、技能都要真的读一次才有内容，改一版布局不必等游戏在手上。

截图走 window.grabWindow()：screen.grabWindow() 在同进程第二次会拿到旧帧，
而且透明悬浮层会被抓成桌面（实测过）。
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import cv2                                                    # noqa: E402
from PySide6.QtCore import QTimer, QUrl, Qt                    # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter     # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine                # noqa: E402
# 必须 import 一下：PySide 是按"已导入的类"决定实例包成哪个包装类的，
# 不导入 QQuickWindow，engine 返回的窗口就只有 QWindow 的方法，grabWindow 会没有。
from PySide6.QtQuick import QQuickWindow                       # noqa: E402,F401

# 截图进程不碰用户的窗口状态：不然上一次跑完写下的尺寸会污染下一次渲染
os.environ["CHAITA_NO_UI_STATE"] = "1"

from chaita.ui import main as ov                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "docs", "capture", "h5_miaomiao_212609.png")

SCENARIOS = ("default", "empty", "long", "reading", "error", "collapsed",
             "collapsed-empty", "session", "floor", "flooritems",
             "floorsmall", "folded", "floorpick",
             "monedit", "monparams", "moncustom", "battle", "battleplan",
             "battlecmp", "battleinsert", "battlepick", "battleedit",
             "battleitemedit", "battlemarks", "route", "routechain",
             "routepick", "gridedit", "routeedit", "routeitemedit", "routememo",
             "iconpick", "iconsearch", "iconscroll1", "iconscroll2",
             "iconscroll3", "queue", "chatlong", "compare", "comparehi")

# 造景里的图/数值全部来自 docs/capture 那一局（拆个魔塔 · 通天塔1），
# 见 `_fake_state()` 的表。别在这里塞素材库的怪物图 —— 那是**另一座塔**的画，
# 和「通天塔1 的红头怪」对不上（用户："fixture 不是实际会出现的"）。


def _find_by_name(window, name):
    """按 objectName 找控件（QQuickItem 的视觉子节点不在 QObject 树里，只能自己走）。

    「这一层」小窗、伤害计算、路线链现在都是**独立窗口**，所以每个顶层窗口都要走一遍。
    """
    for host in _host_windows(window):
        stack = list(host.contentItem().childItems())
        while stack:
            node = stack.pop()
            if node.objectName() == name:
                return node
            stack.extend(node.childItems())
    return None


def _host_windows(main):
    """主窗口 + 它开出来的所有子窗口（这一层 / 伤害计算 / 路线链）。"""
    hosts = [main]
    for other in QGuiApplication.topLevelWindows():
        if other is main or not hasattr(other, "contentItem"):
            continue
        if other.isVisible():
            hosts.append(other)
    return hosts


def _sheet_window(name=""):
    """找出「这一层」那扇真窗口（objectName = floorSheetWindow）。"""
    for other in QGuiApplication.topLevelWindows():
        if other.objectName() != "floorSheetWindow":
            continue
        if not hasattr(other, "contentItem"):
            continue
        if name and str(other.property("sheetName") or "") != name:
            continue
        return other
    return None


def open_sheet(window, name, after=None):
    """开一层小窗，并把它摆回"应用本来想放的位置"。

    截图进程把主窗口挪到了屏幕外（-6000,-6000），小窗是真窗口，clampPos() 会把它
    拉回屏幕里 —— 那样拼出来的图里小窗会跑到主窗口外面几米远。这里按
    floorPositions 里记下的原位置放回去，拼图才对得上。

    小窗是 `Qt.callLater` 里创建的（见 syncFloorSheets），调用完这一行它还没出来，
    所以要等一个事件循环再摆位置。
    """
    window.openFloorSheet(name)

    def place():
        sheet = _sheet_window(name)
        if sheet is None:
            return
        positions = window.property("floorPositions")
        positions = (positions.toVariant()
                     if hasattr(positions, "toVariant") else positions)
        position = (positions or {}).get(name) or {}
        if position.get("x") is not None:
            sheet.setX(int(position["x"]))
        if position.get("y") is not None:
            sheet.setY(int(position["y"]))
        sheet.show()
        if after is not None:
            after(sheet)

    QTimer.singleShot(80, place)


def _battle_window(window):
    """伤害计算那扇窗（QML 里 `win.battleWindow`）。"""
    value = window.property("battleWindow")
    if value is None:
        return None
    if hasattr(value, "toQObject"):
        value = value.toQObject()
    return value


def _route_window(window):
    """路线链那扇窗（QML 里 `win.routeWindow`）。"""
    value = window.property("routeWindow")
    if value is None:
        return None
    if hasattr(value, "toQObject"):
        value = value.toQObject()
    return value


def scroll_sheet_to_items(window, name):
    """把「这一层」的清单滚到资源那一段（截图要看资源行）。"""
    flick = _find_by_name(window, "floorFlick")
    if flick is None:
        return
    content = float(flick.property("contentHeight") or 0)
    view = float(flick.height() or 0)
    flick.setProperty("contentY", max(0.0, content - view))


def _compare_route(monster_first, icon=""):
    """一条路线的 steps：红头怪 + 小蝙蝠 + 红宝石，宝石放前/放后（掉血不一样）。

    每只怪都带**坐标**（层 + 行列，和这一层 grid 里记的那几格一致）：
    路线对比表只画「缩略图 + 坐标」，点一行还要在地图上圈出这一格。
    """
    monster = {"kind": "monster", "name": "红头怪", "hp": 80,
               "atk": 25, "def": 1, "count": 1, "skills": [],
               "icon": icon, "floor": "通天塔1", "row": 5, "col": 5}
    bat = {"kind": "monster", "name": "小蝙蝠", "hp": 100,
           "atk": 30, "def": 3, "count": 1, "skills": [],
           "icon": "", "floor": "通天塔1", "row": 3, "col": 9}
    gem = {"kind": "item", "name": "红宝石", "effect": "攻击力 +1",
           "icon": "gem_red", "count": 1}
    return [monster, gem, bat] if monster_first else [gem, bat, monster]


def _compare_scenario(window, controller):
    """摆三条路线（同一个怪在不同路线的掉血），对比窗贴到主窗口右边。

    缩略图借素材库里一张真图（这一局的怪物手册没裁图），坐标用这一层的
    grid 里真有的那几格；预览主窗口被挪到 -6000，所以对比窗要跟着挪过去，
    出图才紧凑（以前没挪，拼出来是 9480×9276 的空画布）。
    """
    icon = str(controller.libraryUrl("monster/xinxin_redSlime") or "")
    window.openCompare()
    window.compareAdd(_compare_route(True, icon), "路线1")
    window.compareAdd(_compare_route(False, icon), "路线2")
    window.compareAdd(_compare_route(True, icon), "路线3")
    compare = window.property("compareWindow")
    compare = compare.toQObject() if hasattr(compare, "toQObject") else compare
    if compare is not None:
        compare.setX(window.x() + window.width() + 8)
        compare.setY(window.y() + 40)
    QGuiApplication.processEvents()
    return compare


def open_battle(window, controller, compute=True, plans=2):
    """打开伤害计算，摆到主窗口旁边。

    2026-10-27 第 5 次返工后的形状（用户："一行！！！"）：一次计算 = 一整行，
    横向一条链"勇者 → 怪 → 宝石 → 怪"。这里摆两行不同顺序的条件，
    好让截图里能一眼看出"怎么对比不同排序的掉血"。
    """
    window.openBattle()
    battle = _battle_window(window)
    if battle is None:
        return None
    battle.setX(window.x() + window.width() + 8)
    battle.setY(window.y() + 30)
    battle.show()
    # 英雄数值用这一局的真值（生命 53 / 攻击 3 / 防御 2，见 `_fake_state()`）。
    # 以前这里塞 50000/120 是"为了截图好看"，但那是实际不会出现的一手牌；
    # 真实的结果就是打不过通天塔1 的怪 —— 那也正是这个界面该显示的东西。
    for key, value in (("hp", "53"), ("atk", "3"),
                       ("def", "2"), ("mdef", "")):
        window.battleSetHero(key, value)
    monsters = {str(entry.get("name") or ""): entry
                for entry in controller.battleMonsters()}
    gem = next((entry for entry in controller.battleItems()
                if "红宝石" == str(entry.get("name") or "")), None)
    order = [name for name in ("红头怪", "骷髅人", "大蝙蝠") if name in monsters]
    for name in order:                       # 第 1 行：红头怪 → 骷髅人 → 大蝙蝠
        window.battleAddMonster(monsters[name])
    if gem is not None:
        window.battleAddItem(gem)            # 红宝石接在第 1 行尾巴上
    if plans > 1:
        # 第 2 行：换个顺序（宝石先吃，再 大蝙蝠 → 骷髅人 → 红头怪），对比总掉血
        window.battleAddPlan()
        if gem is not None:
            window.battleAddItem(gem)
        for name in reversed(order):
            window.battleAddMonster(monsters[name])
    if compute:
        rows = window.property("battlePlans")
        rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
        for i in range(len(rows or [])):
            window.battleComputePlan(i)
    return battle


def _grab_all(main):
    """把主窗口和它开出来的子窗口按**屏幕上的相对位置**拼成一张图。

    它们现在是各自独立的真窗口（「这一层」、伤害计算、路线链），单独 grabWindow()
    只会拍到主窗口，图上看不到别的窗。
    """
    shots = []
    for host in _host_windows(main):
        grab = getattr(host, "grabWindow", None)
        if grab is None:
            continue
        shots.append((host, grab()))
    if not shots:
        return main.grabWindow()
    left = min(host.x() for host, _ in shots)
    top = min(host.y() for host, _ in shots)
    right = max(host.x() + host.width() for host, _ in shots)
    bottom = max(host.y() + host.height() for host, _ in shots)
    dpr = QGuiApplication.primaryScreen().devicePixelRatio() or 1.0
    width = max(1, int(round((right - left) * dpr)))
    height = max(1, int(round((bottom - top) * dpr)))
    image = QImage(width, height, QImage.Format_ARGB32)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    for host, shot in shots:
        painter.drawImage(host.x() - left, host.y() - top, shot)
    painter.end()
    return image


def _quiet_crash_dialogs() -> None:
    """别让测试进程的崩溃在桌面上弹"Python.exe - 应用程序错误"。"""
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


def _sample():
    """拿一张真实截图当素材（地图缩略图用它）。"""
    import numpy as np
    if not os.path.exists(SAMPLE):
        return None
    return cv2.imdecode(np.fromfile(SAMPLE, dtype=np.uint8), cv2.IMREAD_COLOR)


def _map_shot(image):
    """真·地图截图：**和「读地图」存下来的那张一样，只有地图区域**。

    以前这里直接拿整窗截图当缩略图 —— 带着浏览器标签栏和左边的生命/攻击/钥匙面板，
    而真实存下来的图上根本没有这些（`read.map_snapshot()` 按塔的区域裁过）。
    用户："你测试用的地图都带人物信息，实际根本不可能"。
    """
    from chaita.game import read as game_read
    from chaita.game import towers
    if image is None:
        return ""
    shot = game_read.map_snapshot(towers.H5_MOTA, image)
    if shot is None or not getattr(shot, "size", 0):
        return ""
    return ov._save_thumb(shot, "preview_map", width=400)


def _fake_state():
    """造景用的数据必须**是实际会出现的一局**（用户："fixture 不是实际会出现的"）。

    全部来自 `docs/capture` 里录下的同一局（拆个魔塔 · 通天塔1）：

    | 来源 | 用在哪 |
    |---|---|
    | `_repro2.png`（按塔裁过） | 这一层的地图截图 |
    | `_manual_repro.png` | 下面这 5 只怪的 生命/攻击/防御/经验（手册页上的真数值） |
    | 日志 `read.status` | 塔名「拆个魔塔」、层「通天塔1」、生命 53 |

    没真值的地方（这一层各几只、资源几个）给的是"这层会出现"的量级，不再出现
    以前那种「两张同一个截图当两层」「21000万」的组合。
    """
    image = _sample()
    shot_url = _map_shot(image)

    maps = [
        {"floor": "通天塔1", "url": shot_url,
         # 刷新地图时 AI 记下的"每个格子有什么"（路线链预填用；行列固定 13×13）。
         "grid": {"cells": [
             {"row": 3, "col": 9, "kind": "monster", "name": "小蝙蝠"},
             {"row": 5, "col": 5, "kind": "monster", "name": "红头怪"},
             {"row": 5, "col": 6, "kind": "item", "name": "红宝石"},
             {"row": 6, "col": 6, "kind": "item", "name": "红血瓶"},
             {"row": 8, "col": 3, "kind": "monster", "name": "青头怪"}]},
         "mons": [
            {"name": "红头怪", "count": 4},
            {"name": "骷髅人", "count": 1},
            {"name": "小蝙蝠", "count": 3},
            {"name": "青头怪", "count": 2},
            {"name": "大蝙蝠", "count": 1},
        ], "items": [
            {"name": "红血瓶", "effect": "体力 +150", "count": 3,
             "icon": "potion_red"},
            {"name": "黄钥匙", "effect": "可以打开一扇黄门", "count": 2,
             "icon": "key_yellow"},
            {"name": "红宝石", "effect": "攻击力 +1", "count": 2,
             "icon": "gem_red"},
            # 多段效果（黄宝石加三样）和"武器/防具默认 0"也摆进来：
            # 这两种行是截图要看的，别只有单段效果的样本
            {"name": "黄宝石", "count": 1,
             "effect": "攻击力 +1 · 防御力 +1 · 魔防 +2", "icon": "gem_yellow"},
            {"name": "铁盾", "count": 1, "effect": "防御力 +0",
             "icon": "shield"},
        ]},
    ]
    # 手册页上的真数值（`docs/capture/_manual_repro.png`）。
    # 技能一栏：骷髅人带一个**带参数的技能**（用户自己从下拉里加的，app 允许），
    # 青头怪带开关/二选一那种（monparams 场景要看"吸血 30% / 领域 九宫格"）。
    monsters = [
        {"name": "红头怪", "hp": "80", "atk": "25", "def": "1", "exp": "1",
         "gold": "", "count": 4, "skills": "", "skill_items": [], "icon": ""},
        {"name": "骷髅人", "hp": "200", "atk": "50", "def": "10", "exp": "1",
         "gold": "", "count": 1, "skills": "破甲",
         "skill_items": [{"name": "破甲", "value": "", "code": "7",
                          "params": {"defValue": "50"}}], "icon": ""},
        {"name": "小蝙蝠", "hp": "100", "atk": "30", "def": "3", "exp": "1",
         "gold": "", "count": 3, "skills": "", "skill_items": [], "icon": ""},
        {"name": "青头怪", "hp": "100", "atk": "26", "def": "3", "exp": "1",
         "gold": "", "count": 2, "skills": "吸血 领域",
         "skill_items": [{"name": "吸血", "value": "", "code": "11",
                          "params": {"value": "30", "add": True}},
                         {"name": "领域", "value": "", "code": "15",
                          "params": {"zoneSquare": "九宫格", "range": "1",
                                     "value": "50"}}], "icon": ""},
        {"name": "大蝙蝠", "hp": "120", "atk": "35", "def": "5", "exp": "3",
         "gold": "", "count": 1, "skills": "", "skill_items": [], "icon": ""},
    ]
    tasks = [
        {"id": 3, "state": "done", "text": "通天塔1", "url": shot_url,
         "started": time.time() - 12},
    ]
    status = {"hp": "53", "atk": "3", "def": "2", "gold": "4",
              "keys": {"yellow": 1, "blue": 0, "red": 0, "green": 0}}
    return maps, monsters, tasks, status


def _long_state(maps, monsters):
    """层数和怪都堆到要滚动：检查一屏放不下时的滚动条和裁切。

    同一座塔里多读了几层，但**只有通天塔1 有截图**（真实情况：还没读过的层
    只有一条记录、没有图），所以后面的层 `url` 是空的 —— 不再拿同一张图当好几层。
    """
    shot = maps[0]["url"]
    extra_maps = [{"floor": "通天塔%d" % n, "url": "",
                   "mons": [{"name": "红头怪", "count": 2},
                            {"name": "小蝙蝠", "count": 1}], "items": []}
                  for n in range(2, 8)]
    # 怪也用同一张手册页上的（数量堆大，看长列表时的滚动）
    extra_mons = [dict(monster, count=(monster.get("count") or 1) * 3)
                  for monster in monsters]
    del shot
    return maps + extra_maps, monsters + extra_mons


def _blank(controller):
    """全空状态（没有读之前的样子），用来检查空态。"""
    controller._map_history = []
    controller._monsters = []
    controller._tasks = []
    controller._last_status = {}
    controller._status_at = ""
    controller._tower_label = ""
    controller._chat_log = []
    controller._error_text = ""


def main() -> int:
    _quiet_crash_dialogs()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "docs", "capture", "_preview.png")
    # 第二参数以前是"窗口高"，新版窗口高度由内容撑出来，留着只为兼容旧命令
    scenario = sys.argv[3] if len(sys.argv) > 3 else ""
    if scenario == "":
        scenario = "default"
    if scenario not in SCENARIOS:
        print("不认识的场景 %r，可选：%s" % (scenario, ", ".join(SCENARIOS)))
        return 2

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("ChaitaAssistant")

    controller = ov.Controller()
    maps, monsters, tasks, status = _fake_state()
    if scenario == "long":
        maps, monsters = _long_state(maps, monsters)
    controller._map_history = maps
    controller._monsters = monsters
    controller._tasks = tasks
    controller._last_status = status
    # 走一遍 _apply_status：截图里才会出现"HH:MM 读取"
    controller._apply_status(status)
    controller._tower_label = "拆个魔塔 通天塔1"
    controller._attr_text = "生命 53   攻击 3   防御 2"
    controller._chat_log = [
        {"who": "你", "text": "红头怪还剩几只？", "at": "14:32"},
        {"who": "AI", "text": "通天塔1 还有 4 只，骷髅人剩 1 只。", "at": "14:32"},
    ]
    # 磁盘上的旧存档会带出"上次的那一局"：除 session 场景外一律清掉
    controller._session_hint = ""
    if scenario in ("empty", "collapsed-empty"):
        _blank(controller)
    elif scenario == "reading":
        # reading 走的是 _reading 这个标记（reading.py 里开工/收工各改一次）
        controller._reading = True
    elif scenario == "error":
        controller._error_text = "读不到局面：读操作超时"
    elif scenario == "session":
        # 上次退出时留下的恢复提示（只有真有存档才会出现）
        controller._session_hint = "10-26 15:20 · 6 层 / 14 只怪"
    elif scenario == "queue":
        # 并行读取：地图和手册各跑一条，外加一条失败的、一条成功的
        controller._reading = True
        controller._tasks = [
            {"id": 9, "seq": 9, "state": "running", "text": "读取中",
             "mode": "map", "started": time.time() - 12},
            {"id": 8, "seq": 8, "state": "running", "text": "读取中",
             "mode": "monsters", "started": time.time() - 4},
            {"id": 7, "seq": 7, "state": "failed",
             "text": "读不到局面：读操作超时", "mode": "map",
             "started": time.time() - 60},
            {"id": 6, "seq": 6, "state": "done", "text": "通天塔1",
             "mode": "map", "started": time.time() - 120},
        ]
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    ov.load_into(engine)
    if not engine.rootObjects():
        print("QML 加载失败")
        return 1

    window = engine.rootObjects()[0]
    controller.attach(window)
    window.setProperty("appTitle", ov.APP_TITLE)
    window.setProperty("heroIcon", ov.HERO_ICON)
    window.setProperty("iconBase", ov.ICON_BASE)
    window.setProperty("itemBase", ov.ITEM_BASE)
    window.setProperty("collapsed", False)
    # 截图工具也不该占用户的屏幕：挪到屏幕外（grabWindow 照样能渲染，实测过）
    window.setProperty("x", -6000)
    window.setProperty("y", -6000)
    controller.statusTextChanged.emit()
    controller.mapHistoryChanged.emit()
    controller.monstersChanged.emit()
    controller.tasksChanged.emit()
    controller.chatLogChanged.emit()
    controller.chatReplyChanged.emit()
    controller.readingChanged.emit()
    controller.sessionHintChanged.emit()
    window.show()

    def _walk():
        stack = list(window.contentItem().childItems())
        items = []
        while stack:
            node = stack.pop()
            items.append(node)
            stack.extend(node.childItems())
        return items

    def _report():
        names = [item.objectName() for item in _walk()]
        texts = {}
        for item in _walk():
            key = item.objectName()
            if key in ("towerLabel", "monAgg", "skillAgg", "readTip",
                       "errorText", "appTitle"):
                value = item.property("text")
                if value is not None:
                    texts[key] = value
        print("size %dx%d collapsed=%r" % (window.width(), window.height(),
                                           window.property("collapsed")))
        print("dpr %.3f" % (QGuiApplication.primaryScreen().devicePixelRatio()
                            or 1.0))
        print("tower %r" % (texts.get("towerLabel"),))
        print("monAgg %r skillAgg %r" % (texts.get("monAgg"),
                                         texts.get("skillAgg")))
        print("readTip %r error %r" % (texts.get("readTip"),
                                       texts.get("errorText")))
        print("tiles %d monsters %d skills %d chats %d"
              % (names.count("mapTile"), names.count("monRow"),
                 names.count("skillRow"), names.count("chatRowItem")))

    def _start():
        if scenario in ("collapsed", "collapsed-empty"):
            window.setProperty("collapsed", True)
        elif scenario == "folded":
            # 地图/怪物两栏都折叠：看空两格标题（用户："地图和怪物怎么不能折叠"）
            window.setProperty("mapCollapsed", True)
            window.setProperty("monCollapsed", True)
        elif scenario == "reading":
            # 读取中只有"点了读取按钮"才有：地图那栏的按钮显示成「读取中」
            window.setProperty("readingMode", "map")
        elif scenario == "floor":
            # 地图的子界面：打开「通天塔1」那一层
            open_sheet(window, "通天塔1")
        elif scenario == "routememo":
            # 路线备注：路线行边上写"血/攻/防/魔防"（默认），可加字
            path = [{"row": 5, "col": 5}, {"row": 5, "col": 6}]
            window.storeRoute("通天塔1", path)
            window.closeRoute()

            def scroll_to_routes(sheet):
                flick = _find_by_name(sheet, "floorFlick")
                if flick is not None:
                    content = float(flick.property("contentHeight") or 0)
                    view = float(flick.height() or 0)
                    flick.setProperty("contentY", max(0.0, content - view))

            open_sheet(window, "通天塔1", scroll_to_routes)
        elif scenario == "flooritems":
            # 清单滚到资源那一段：看资源行（图标 + 名字 + 效果 + 数量）
            open_sheet(window, "通天塔1", lambda _sheet: scroll_sheet_to_items(
                window, "通天塔1"))
        elif scenario == "floorsmall":
            # 小窗拉到很矮时，加资源的下拉菜单要能完整显示（用户反馈）
            window.saveFloorSize("通天塔1", 300, 250)
            open_sheet(window, "通天塔1", lambda sheet: window.openPickMenu(
                "item", "通天塔1", _find_by_name(window, "floorAddItem"), -1,
                sheet))
        elif scenario == "floorpick":
            # 加怪的下拉菜单（用户："加怪、加资源怎么不是下拉菜单"）
            open_sheet(window, "通天塔1", lambda sheet: window.openPickMenu(
                "mon", "通天塔1", _find_by_name(window, "floorAddMon"), -1,
                sheet))
        elif scenario == "battle":
            # 伤害计算：加两只怪 + 一个宝石，点「计算」看结果
            open_battle(window, controller)
        elif scenario == "battleplan":
            # 还没点「计算」：每行只有"待计算"（用户："点计算后出结果"）
            open_battle(window, controller, compute=False)
        elif scenario == "battlecmp":
            # 两行不同顺序摆一起，右边的总掉血对着看（用户："我怎么对比不同排序的掉血"）
            open_battle(window, controller)
        elif scenario == "battleinsert":
            # 点链上的箭头 → 菜单写"插在第 k 格前面"（用户："点箭头要能插入"）
            battle = open_battle(window, controller, plans=1, compute=False)
            if battle is not None:
                window.openBattleMenu(0, 1)
                battle.show()
        elif scenario == "battlepick":
            # 问号菜单的"资源"页（用户："应该只有两个标签页分别是怪物和资源"）
            battle = open_battle(window, controller, plans=1, compute=False)
            if battle is not None:
                window.openBattleMenu(0, -1)
                window.battleSwitchTab("item")
                battle.show()
        elif scenario == "battleedit":
            # 点缩略图改参数（用户："点击缩略图可以修改参数"）
            battle = open_battle(window, controller, plans=1)
            if battle is not None:
                window.battleEditStep(0, 2)    # 青头怪：带"吸血 30%"这种参数
                battle.show()
        elif scenario == "battleitemedit":
            # 资源那格的参数编辑（用户："调整宝石效果的界面怎么有两个加号"、
            # "数量的文本框太长了"）—— 第 1 行第 4 格是红宝石
            battle = open_battle(window, controller, compute=False, plans=1)
            if battle is not None:
                window.battleEditStep(0, 3)
                battle.show()
        elif scenario == "battlemarks":
            # 宝石缩略图左下角的效果标记（用户 2026-10-28）：红=攻击、蓝=防御、
            # 绿=魔防；黄宝石三样一起加，从上到下 魔防 / 攻击 / 防御
            battle = open_battle(window, controller, compute=False, plans=1)
            if battle is not None:
                for entry in controller.battleItems():
                    if str(entry.get("name")) in ("蓝宝石", "黄宝石"):
                        window.battleAddItem(entry)
                battle.show()
        elif scenario == "route":
            # 路线提取：长按起步、拖过相邻格画红线（docs/ROUTE.md）。
            # 行列固定 13×13，红线和格子对得上。
            def draw_route(sheet):
                layer = _find_by_name(sheet, "routeLayer")
                if layer is None:
                    return
                layer.setProperty("cells", [
                    {"row": 5, "col": 4}, {"row": 5, "col": 5},
                    {"row": 5, "col": 6}, {"row": 6, "col": 6},
                    {"row": 6, "col": 5}])
                shot = _find_by_name(sheet, "floorShotBox")
                picture = _find_by_name(sheet, "floorShot")
                print("routeLayer cell %.2f rect %.1fx%.1f @%.1f,%.1f "
                      "box %.1fx%.1f image %.1fx%.1f painted %.1fx%.1f"
                      % (layer.property("cell"), layer.width(), layer.height(),
                         layer.x(), layer.y(),
                         shot.width() if shot else 0,
                         shot.height() if shot else 0,
                         picture.width() if picture else 0,
                         picture.height() if picture else 0,
                         picture.property("paintedWidth") if picture else 0,
                         picture.property("paintedHeight") if picture else 0))

            open_sheet(window, "通天塔1", draw_route)
        elif scenario in ("routechain", "routepick", "routeedit", "routeitemedit"):
            # 路线链：勇者 → 格6,5 → 格6,6 …，格子里的东西来自"刷新地图时记下的
            # 每一格有什么"；点「计算」以后掉血写格后、总掉血在右端。
            path = [{"row": 5, "col": 4}, {"row": 5, "col": 5},
                    {"row": 5, "col": 6}, {"row": 6, "col": 6},
                    {"row": 6, "col": 5}, {"row": 7, "col": 3}]
            index = controller.saveRoute("通天塔1", path)
            window.openRoute("通天塔1", index)
            route_win = _route_window(window)
            if route_win is not None:
                route_win.setX(window.x() + window.width() + 8)
                route_win.setY(window.y() + 30)
                route_win.show()
            if scenario == "routechain":
                window.routeCompute()
            elif scenario == "routepick":
                # 点开第 2 格的下拉：怪 / 资源两个标签页 + 门 / 清空
                QTimer.singleShot(250, lambda: window.openRouteMenu(1))
            elif scenario == "routeedit":
                # 点第 2 格（红头怪）的缩略图 = 改参数卡片（和伤害计算同一个长相）
                QTimer.singleShot(250, lambda: window.routeEditStep(1))
            else:
                # 点资源那格（红宝石）的缩略图
                QTimer.singleShot(250, lambda: window.routeEditStep(2))
        elif scenario == "gridedit":
            # 格子编辑模式：地图盖 13×13 坐标系，词条下面标"位置 x,y"
            window.gridEditToggle("通天塔1")
            open_sheet(window, "通天塔1")
        elif scenario == "monedit":
            # 怪物编辑界面：开骷髅人（它带"破甲"这种有数值参数的技能）
            window.openMonster(1)
        elif scenario == "monparams":
            # 开关 / 二选一参数（吸血、领域）
            window.openMonster(3)
        elif scenario == "moncustom":
            # 自定义技能：名称和介绍都能写（用户："自定义怎么只能写技能名称
            # 不能写技能介绍"）
            window.openMonster(1)
            window.addSkill("")
            rows = window.property("monSkills")
            rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
            index = len(rows) - 1
            window.setSkill(index, "name", "召唤小怪")
            # 介绍框自己带 placeholder，这里把字填进去（截图要看"写完的样子"）
            field = _find_by_name(window, "monSkillEffectEdit")
            if field is not None:
                field.setProperty("text", "每两回合召唤一只小怪，最多同时存在 3 只")
        elif scenario == "chatlong":
            # 只显示一问一答 + 长回答折行（不截断）
            controller._chat_log = [
                {"who": "你", "text": "第一问", "at": "14:20"},
                {"who": "AI", "text": "第一答", "at": "14:20"},
                {"who": "你", "text": "通天塔1还剩什么？", "at": "14:31"},
                {"who": "AI",
                 "text": "通天塔1 这一层还有红头怪 4 只（其中 2 只已经打过）、"
                         "骷髅人 1 只；下楼前记得先拿红血瓶，"
                         "钥匙只有 1 把黄钥匙，青头怪那两只要小心。",
                 "at": "14:31"},
            ]
            controller.chatLogChanged.emit()
        elif scenario == "compare":
            # 路线对比：摆三条路线，比同一只怪在不同路线的掉血
            _compare_scenario(window, controller)
        elif scenario == "comparehi":
            # 点对比表里的一行 → 那一层的地图上把这一格圈出来
            #（用户："最好点击后会在地图内高亮"）
            compare = _compare_scenario(window, controller)
            rows = window.compareRows()
            rows = rows.toVariant() if hasattr(rows, "toVariant") else rows

            def beside_compare(sheet):
                if compare is not None:
                    sheet.setX(compare.x() + compare.width() + 8)
                    sheet.setY(compare.y())
                sheet.show()

            open_sheet(window, "通天塔1", beside_compare)
            if rows:
                window.compareHighlight(rows[0])

        elif scenario == "iconpick":
            # 选图界面：素材库里有大量动画帧，这里要看到去重后的样子
            window.openMonster(0)
            window.setProperty("iconPicker", True)
        elif scenario == "iconsearch":
            # 素材库搜索：按名字过滤（只剩史莱姆那几只）
            window.openMonster(0)
            window.setProperty("iconPicker", True)
            # 搜索态要按下"搜索"页签才出现，预览里直接置位
            window.setProperty("iconSearchMode", True)
            window.setProperty("iconQuery", "史莱姆")
        elif scenario.startswith("iconscroll"):
            # 素材库往下翻，看分类是不是真的一类挨着一类（排查顺序用）
            window.openMonster(0)
            window.setProperty("iconPicker", True)
            offset = {"iconscroll1": 0, "iconscroll2": 1,
                      "iconscroll3": 2}.get(scenario, 0)

            def scroll(_offset=offset):
                flick = _find_by_name(window, "iconFlick")
                if flick is None:
                    return
                view = float(flick.height() or 0)
                flick.setProperty("contentY", view * _offset)

            QTimer.singleShot(200, scroll)
        QTimer.singleShot(800, _grab)

    def _grab():
        shot = _grab_all(window)
        shot.save(out, "PNG")
        _report()
        print("saved", out, shot.width(), "x", shot.height())
        app.quit()

    QTimer.singleShot(500, _start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
