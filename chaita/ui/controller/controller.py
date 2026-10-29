"""Controller：QML 看见的那一个对象（信号 + 属性 + 启动时的一次性装配）。

线程/任务队列在 `jobs.py`，窗口尺寸/拖动/动画在 `window.py`，
上次会话的提示在 `session.py`；这里只留"对外的那张脸"和 `__init__`。
"""

import os
import threading
import time

from .. import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Property, QObject, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication

from ..constants import DRAG_INTERVAL_MS, MON_DRAG_INTERVAL_MS, SESSION_PATH
from ..toolkit.library import _load_monster_templates, _load_skill_catalog
from ..toolkit.state import (_load_session, _load_ui_state, _save_session,
                             _save_ui_state, _session_hint)
from .battle import BattleMixin
from .chat import ChatMixin
from .floors.mixin import FloorsMixin
from .jobs import JobsMixin
from .monsters.mixin import MonstersMixin
from .reading.mixin import ReadingMixin
from .session import SessionMixin
from .status import StatusMixin
from .window import WindowMixin


class Controller(JobsMixin, WindowMixin, SessionMixin, ChatMixin,
                 BattleMixin, FloorsMixin, MonstersMixin, ReadingMixin,
                 StatusMixin, QObject):
    sizeAnimDone = Signal()

    sessionHintChanged = Signal()

    readingChanged = Signal()

    statusTextChanged = Signal()

    mapHistoryChanged = Signal()

    monstersChanged = Signal()

    # 技能区依赖两个来源（怪物记录 + 地图上加过的怪），单一 notify 会漏刷新：
    # 以前在地图里加怪只发 mapHistoryChanged，技能区就不更新（用户："加了怪技能没同步"）。
    skillStatsChanged = Signal()

    chattingChanged = Signal()

    chatReplyChanged = Signal()

    # 对话记录：一整段对话（谁说了什么），不是只有最后一句
    chatLogChanged = Signal()

    tasksChanged = Signal()

    # 某一行刚存好（"item:地下30:0"）：界面用它让那一格底色闪一下，让用户知道改生效了
    savedKeyChanged = Signal()

    # 拖拽排序：从哪一行拖、现在落在哪一行（-1 = 没在拖）
    monDragChanged = Signal()

    # 正在统计哪一层的怪物数量（空 = 没在统计）：那一行的 ↻ 显示成「…」
    countingChanged = Signal()

    # 人物状态锁换了（锁住后「读取」不改状态面板）
    statusLockedChanged = Signal()

    # 后台线程 → 界面线程的通道：传一个可调用对象过去，在界面线程里执行
    uiCall = Signal(object)

    activeReads = Property(int, JobsMixin._get_active_reads, notify=readingChanged)

    reading = Property(bool, JobsMixin._get_reading, notify=readingChanged)

    tasks = Property("QVariantList", JobsMixin._get_tasks, notify=tasksChanged)

    statusText = Property(str, StatusMixin._get_status_text, notify=statusTextChanged)

    attrText = Property(str, StatusMixin._get_attr_text, notify=statusTextChanged)

    itemsText = Property(str, StatusMixin._get_items_text, notify=statusTextChanged)

    goldText = Property(str, StatusMixin._get_gold_text, notify=statusTextChanged)

    # 结构化状态（dict），QML 侧拿它拼"图标 + 数值"
    statusData = Property("QVariant", StatusMixin._get_status_data,
                          notify=statusTextChanged)

    # 人物状态锁：锁住后「读取」不再改状态面板
    #（用户："加一个锁，点击后人物状态不会因为读取而改变"）
    statusLocked = Property(bool, StatusMixin._get_status_locked,
                            notify=statusLockedChanged)

    countingFloor = Property(str, FloorsMixin._get_counting_floor, notify=countingChanged)

    # 上次会话还有记录时给一句提示（空串 = 没有/不用提示）
    sessionHint = Property(str, SessionMixin._get_session_hint, notify=sessionHintChanged)

    # 面板最后一次读到数据的时间（"23:51"），空串表示还没读过
    statusAt = Property(str, StatusMixin._get_status_at, notify=statusTextChanged)

    # 地图截图历史，QML 侧当字符串数组用（每项是 file:// URL）
    mapHistory = Property("QVariantList", FloorsMixin._get_map_history,
                          notify=mapHistoryChanged)

    # 怪物记录：每项 {name, hp, atk, def, exp, count, icon(file:// URL), skill_items}
    monsters = Property("QVariantList", MonstersMixin._get_monsters, notify=monstersChanged)

    # 常见怪物模板（名字 + 生命/攻/防/经验），给「＋」的下拉用
    monsterTemplates = Property("QVariantList", MonstersMixin._get_monster_templates,
                                notify=monstersChanged)

    skillStats = Property("QVariantList", MonstersMixin._get_skill_stats,
                          notify=skillStatsChanged)

    # 地图记录里出现过的怪名（技能区/技能明细只按这些算）
    mapMonsterNames = Property("QVariantList", MonstersMixin._map_monster_names,
                               notify=mapHistoryChanged)

    # 技能下拉的候选（库里全部已知技能 + 手打/读到的）
    skillCatalog = Property("QVariantList", MonstersMixin._get_skill_catalog,
                            notify=monstersChanged)

    towerLabel = Property(str, MonstersMixin._get_tower_label, notify=statusTextChanged)

    chatReply = Property(str, ChatMixin._get_chat_reply, notify=chatReplyChanged)

    # 对话记录：[{who:"你"/"AI", text:"…"}]。界面下方「对话」那一段读它，
    # 下一句发出去时也拿它当上下文（所以它是功能，不只是装饰）。
    chatLog = Property("QVariantList", ChatMixin._get_chat_log,
                       notify=chatLogChanged)

    # 读取失败的原因。界面上直接显示，不然用户只看到"点了没反应"
    errorText = Property(str, ChatMixin._get_error_text, notify=chatReplyChanged)

    chatting = Property(bool, ChatMixin._get_chatting, notify=chattingChanged)

    updating = Property(bool, StatusMixin._get_updating, notify=readingChanged)

    savedKey = Property(str, FloorsMixin._get_saved_key, notify=savedKeyChanged)

    monDragFrom = Property(int, MonstersMixin._get_mon_drag_from,
                           notify=monDragChanged)

    monDragTo = Property(int, MonstersMixin._get_mon_drag_to, notify=monDragChanged)

    @Slot(str)
    def clipboardCopy(self, text: str) -> None:
        """把一段文本写进系统剪贴板（「复制路线」是真复制，别的程序也能粘贴）。"""
        QGuiApplication.clipboard().setText(str(text))

    @Slot(result=str)
    def clipboardText(self) -> str:
        """读系统剪贴板（「粘贴」从真剪贴板取，不是内存里的临时变量）。"""
        return QGuiApplication.clipboard().text()

    def __init__(self) -> None:
        super().__init__()
        self._win = None
        # 后台线程改界面状态一律通过这条队列走，避免和 QML 抢数据
        self.uiCall.connect(self._run_ui_call, Qt.QueuedConnection)
        self._drag_active = False
        self._drag_offset = (0, 0)
        self._last_pos = None
        self._timer = QTimer(self)
        self._timer.setInterval(DRAG_INTERVAL_MS)
        self._timer.timeout.connect(self._tick_drag)

        # 怪物行拖拽排序：按住行之后由这个定时器读光标算落点
        self._mon_drag = None
        self._mon_drag_timer = QTimer(self)
        self._mon_drag_timer.setInterval(MON_DRAG_INTERVAL_MS)
        self._mon_drag_timer.timeout.connect(self._tick_mon_drag)

        # 尺寸动画。QML 侧没法逐帧改窗口几何（Window.height 上的 Behavior 和
        # NumberAnimation 都不生效，实测直接跳变），所以插值放到 Python 做。
        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._tick_size)
        self._anim_from = (0, 0)
        self._anim_to = (0, 0)
        self._anim_start = 0.0
        self._anim_ms = 180

        # 窗口位置/大小：拖动、缩放、折叠动画都会触发变更，攒 600ms 再写盘，
        # 别每次移动都写文件（拖动时一秒几十次）。
        self._pending_geometry = None
        self._geometry_ready = False
        self._state_timer = QTimer(self)
        self._state_timer.setSingleShot(True)
        self._state_timer.setInterval(600)
        self._state_timer.timeout.connect(self._flush_ui_state)

        # 读游戏状态是网络调用（实测 2~5 秒），必须放后台线程，否则会冻住界面。
        self._reading = False
        self._status_text = ""
        self._attr_text = ""
        self._items_text = ""
        self._gold_text = ""
        self._tower_label = ""
        # 面板数据是什么时候读到的（"23:51"），让用户知道该不该重读
        self._status_at = ""
        # 每次读取换文件名，避开 QML 的图片缓存（否则会显示上一次的图）
        self._frame = 0
        # 地图截图历史：每次读取一条。并行读取时每条带自己的 id，结果乱序回来
        # 也只填自己那条，不会互相覆盖。
        self._map_history = []
        self._map_seq = 0          # 每点一次读取 +1，作为这次任务的序号
        # 正在统计数量的那一层（空 = 没有在统计）：界面据此把那行的 ↻ 换成「…」，
        # 不然用户点了之后看不出到底有没有在跑。
        self._counting_floor = ""
        self._status_seq = -1      # 只让序号最大的那次改状态面板
        self._active = 0           # 正在跑的读取任务数
        # 任务队列：每点一次「读取」一条，界面在技能下面列出来。
        # state: running（跑着）/ done（完成，界面上打勾）/ failed（失败，给重试按钮）
        self._tasks = []
        self._task_seq = 0
        # 被用户点"关闭"取消的任务号：结果回来一律丢弃
        self._cancelled = set()
        # 怪物：模型读手册/读地图时报出来的记录（纯文字，没有图标）
        self._monsters = []
        # 对话修正：用户用自然语言指出读取错误
        self._chat_reply = ""
        # 整段对话（含玩家的原话），既是界面上的记录，也是下一句的上下文
        self._chat_log = []
        self._updating = False
        self._chatting = False
        # 每次发话递增；后台线程/超时回调带着旧号回来就别覆盖新结果
        self._chat_token = 0
        self._error_text = ""
        # 刚才哪一行存好了（QML 用它让那一格底色闪一下，1.2 秒后自己清掉）
        self._saved_key = ""
        self._saved_timer = QTimer(self)
        self._saved_timer.setSingleShot(True)
        self._saved_timer.setInterval(1200)
        self._saved_timer.timeout.connect(self._clear_saved)
        self._last_tower = None
        self._last_status = {}
        # 人物状态锁：锁住后读取不改状态面板
        self._status_locked = False

        # 上次退出时存的记录：只在界面上给一句提示，等用户点「恢复」才加载
        self._session = _load_session()
        self._session_hint = _session_hint(self._session)

        # 记住"最近一次前台的窗口进程"，但只在它属于游戏时才用。
        # 点「读取」的那一刻前台是悬浮层自己（pythonw.exe），所以需要短暂采样，
        # 取采样到的最后一个非悬浮层进程 —— 那才是用户刚才在看的窗口。
        self.monstersChanged.connect(self.skillStatsChanged.emit)
        self.mapHistoryChanged.connect(self.skillStatsChanged.emit)
        self._monster_templates = _load_monster_templates()
        self._skill_catalog = _load_skill_catalog()
        self._last_foreground = ""
        self._poll = QTimer(self)
        self._poll.setInterval(120)
        self._poll.timeout.connect(self._sample_foreground)
        self._poll.start()
        # 退出时用：别让后台线程在解释器收尾时还在碰 Qt 对象（会闪退/0xC0000005）
        self._closing = False
        self._threads = []
