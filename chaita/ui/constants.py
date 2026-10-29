"""界面用到的常量、资源路径、进程启动标记。改数值只改这里。"""

import os
import time
# 仓库根下的 logs/：运行期状态（会话记录、窗口位置、崩溃日志）都放这儿
from ..paths import ASSETS as _ASSETS_ROOT, LOGS as _LOGS


# 这个进程的启动标记：临时图片文件名都带上它，重启后不会和上一次撞名。
# （撞名会让 QML/磁盘上的旧图被新图覆盖，看到手册截图变成地图这种怪事。）
_SESSION = time.strftime("%Y%m%d%H%M%S")

APP_TITLE = "拆塔辅助"

# 打开时离屏幕边缘留多少，别贴死
MARGIN = 24

# 上次退出时的"手动记录"（层 + 怪物参数），下次启动只提示、不自动恢复
SESSION_PATH = os.path.join(_LOGS, "last_session.json")

# 窗口位置/大小记在这里（下次启动照原样摆回去）。
# 放 logs 下：这是运行期状态，不是配置；删掉也不影响启动（会回到默认位置）。
UI_STATE_PATH = os.path.join(_LOGS, "ui_state.json")

# 勇者图标：原版 Flash 魔塔 v1.12 的勇者（棕发 / 蓝衣 / 银甲）。
# 素材取自 xhy1999/MagicTower（Java 复刻版，含原版素材）的
# src/main/resources/image/player/player01_1_1.png —— 正面站立帧，原始 32x32。
# 命名规律 player01_<行>_<列>：行 0 背面 / 行 1 正面 / 行 2-3 左右行走。
_ASSETS = _ASSETS_ROOT

HERO_ICON = "file:///" + os.path.join(_ASSETS, "hero_icon.png").replace("\\", "/")

# 状态图标目录（由 tools/make_icons.py 生成）
ICON_BASE = "file:///" + os.path.join(_ASSETS, "icons").replace("\\", "/") + "/"

# 资源图标（血瓶/宝石）：tools/slice_items.py 从用户给的精灵表切出来的无数字版本
ITEM_BASE = "file:///" + os.path.join(_ASSETS, "items").replace("\\", "/") + "/"

# 拖动节流间隔。Windows 鼠标事件约 125Hz，跟着每次事件移动窗口会让 DWM
# 反复重新合成这个透明窗口，观感就是卡。按显示器刷新率节流就顺了。
DRAG_INTERVAL_MS = 8

# 按住鼠标拖动怪物行时，多久看一次光标位置（够跟手，又不至于每个像素都算一遍）
MON_DRAG_INTERVAL_MS = 40

# 无边框窗口（Qt.FramelessWindowHint）会让 Windows 失去边缘缩放与光标反馈。
# 自己在 WM_NCHITTEST 里回答"鼠标在哪个部位"，系统就会把缩放、光标形状、
# 双击标题栏、贴边这些原生行为全都装回来 —— 和普通窗口完全一致。
_BORDER = 6  # 边缘判定宽度（物理像素）

_HTLEFT, _HTRIGHT, _HTTOP, _HTTOPLEFT, _HTTOPRIGHT = 10, 11, 12, 13, 14
_HTBOTTOM, _HTBOTTOMLEFT, _HTBOTTOMRIGHT = 15, 16, 17

# 状态字段的显示名。层数不显示在属性里 —— 地图列表每行就是层数。
_KEY_LABELS = [("yellow", "黄"), ("blue", "蓝"), ("red", "红"), ("green", "绿")]

_SPECIAL_LABELS = [("po", "破"), ("zha", "炸"), ("fei", "飞")]

# 本层的一行里，除了名字/数量/效果，还有两样是"用户自己加的":
#   icon —— 换过的缩略图（手册里没有的怪、素材库里挑的资源图）
#   done —— 打过了 / 拿过了（用户自己在行首勾的）
# 每次按名字重建行（存数量、读数量、AI 重读资源）都要把这两样带过去，
# 否则改一下数量就把缩略图和勾选弄丢了。
_ROW_EXTRA_KEYS = ("icon", "icon_id", "done", "effect_manual")

MAP_HISTORY_LIMIT = 30

# 任务队列最多留多少条
TASK_LIMIT = 20
