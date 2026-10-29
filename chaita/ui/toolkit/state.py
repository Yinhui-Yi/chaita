"""会话记录与窗口状态的读写（logs/ 下那两个 json）。"""

import json
import os
import time

from .. import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtGui import QGuiApplication

from ..constants import MARGIN, SESSION_PATH, UI_STATE_PATH


def _save_session(monsters, floors) -> None:
    """退出时把"手动记录"存一份（不含血量/钥匙这些会过期的东西）。"""
    try:
        data = {
            "saved_at": time.strftime("%H:%M"),
            "monsters": list(monsters or [])[:200],
            "floors": list(floors or [])[:50],
        }
        if not data["monsters"] and not data["floors"]:
            return
        folder = os.path.dirname(SESSION_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temp = SESSION_PATH + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(temp, SESSION_PATH)
    except Exception:
        pass

def _load_session() -> dict:
    """读上次的记录；没有/坏了返回 {}。图片文件已经不在了就把 url 清掉。"""
    try:
        with open(SESSION_PATH, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    monsters = data.get("monsters")
    floors = data.get("floors")
    if not isinstance(monsters, list) or not isinstance(floors, list):
        return {}
    if not monsters and not floors:
        return {}
    cleaned_floors = []
    for entry in floors[:50]:
        if not isinstance(entry, dict):
            continue
        row = dict(entry)
        url = str(row.get("url") or "")
        if url.startswith("file://"):
            path = url[7:].replace("/", os.sep)
            if path.startswith(os.sep) and len(path) > 2 and path[2] == ":":
                path = path[1:]
            if not os.path.exists(path):
                row["url"] = ""
        cleaned_floors.append(row)
    data["floors"] = cleaned_floors
    data["monsters"] = [_fix_monster_icon(one)
                        for one in monsters[:200] if isinstance(one, dict)]
    return data


def _url_missing(url: str) -> bool:
    """`file://` 的图还在不在（不是文件 URL 就当它在）。"""
    url = str(url or "")
    if not url.startswith("file://"):
        return False
    path = url[7:].replace("/", os.sep)
    if path.startswith(os.sep) and len(path) > 2 and path[2] == ":":
        path = path[1:]
    return not os.path.exists(path)


def _fix_monster_icon(entry: dict) -> dict:
    """素材库的图改过名字（`xinxin2_E380.png` → `guard_e380.png`）—— 老记录要能跟上。

    `icon_id`（`monster/<塔>_<贴图键>`）是稳定键，直接按它重新取 url；
    没有 icon_id 的老记录，把 `icon` 里那个文件名拿去问 `library.id_of_file()`
    （贴图键、旧的中文名、现在的新名字都认）；还查不到就是上传图或者真没了，
    这时才把 url 清掉（界面会显示"怪"字占位，而不是一张坏图）。
    """
    row = dict(entry)
    from ... import library
    icon_id = str(row.get("icon_id") or "")
    if icon_id.startswith("monster/"):
        url = library.url_of(icon_id)
        if url:
            row["icon"] = url
            return row
    url = str(row.get("icon") or "")
    if url and _url_missing(url):
        stem = os.path.splitext(os.path.basename(url[7:].replace("/", os.sep)))[0]
        found = library.id_of_file(stem) if stem else ""
        url = library.url_of(found) if found else ""
        row["icon"] = url
        if not url:
            row["icon_id"] = ""
        else:
            row["icon_id"] = found
    return row

def _session_hint(data: dict) -> str:
    """界面上那句提示用的摘要。"""
    if not data:
        return ""
    floors = len(data.get("floors") or [])
    monsters = len(data.get("monsters") or [])
    if not floors and not monsters:
        return ""
    saved_at = str(data.get("saved_at") or "").strip()
    parts = []
    if floors:
        parts.append("%d 层" % floors)
    if monsters:
        parts.append("%d 只怪" % monsters)
    return ("%s · " % saved_at if saved_at else "") + " / ".join(parts)

def _ui_state_enabled() -> bool:
    """截图/测试工具不该动用户的窗口状态（否则上一次的尺寸会污染下一次渲染）。"""
    return not os.environ.get("CHAITA_NO_UI_STATE")

def _load_ui_state() -> dict:
    """读上次记下的窗口状态；没有/坏了都当空。"""
    if not _ui_state_enabled():
        return {}
    try:
        # utf-8-sig：文件可能被记事本/旧 PowerShell 存成带 BOM 的 UTF-8
        with open(UI_STATE_PATH, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

def _save_ui_state(state: dict) -> None:
    """写窗口状态（先写临时文件再替换，别写出半个 JSON）。"""
    if not _ui_state_enabled():
        return
    try:
        folder = os.path.dirname(UI_STATE_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temp = UI_STATE_PATH + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
        os.replace(temp, UI_STATE_PATH)
    except Exception:
        pass

def _geometry_from_state(state: dict, area):
    """把状态里的 x/y/width/height 算成能用的几何；没记录或值不对返回 None。

    area 是屏幕可用区域（QRect）。窗口太宽/太高按屏幕夹住；
    位置至少留 60×40 在屏幕里，免得存了个离谱的坐标下次找不回来。
    """
    if not isinstance(state, dict):
        return None
    try:
        x = int(state.get("x"))
        y = int(state.get("y"))
    except (TypeError, ValueError):
        return None

    width = 340
    height = 700
    try:
        if state.get("width"):
            width = int(state["width"])
        if state.get("height"):
            height = int(state["height"])
    except (TypeError, ValueError):
        return None

    width = max(260, min(900, width))
    height = max(120, min(max(200, area.height() - 8), height))
    x = max(area.x() - width + 60, min(x, area.x() + area.width() - 60))
    y = max(area.y(), min(y, area.y() + area.height() - 40))
    return x, y, width, height

def _apply_ui_state(window) -> bool:
    """按上次的位置摆窗口；没有记录（或不合法）返回 False，交给默认位置。

    **只恢复位置，不恢复尺寸**：新版界面的尺寸是内容撑出来的，
    - 恢复高度 → 内容只有 300 高、窗口却是 800 高，底下留一大片空白
      （用户："折叠后还是有一大片空白"）；
    - 恢复宽度 → 上次拖出来的窄条会被原样带回来，看着像缩水。
    想要更大/更宽的窗口，本次自己拉边缘就行。
    """
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return False
    geometry = _geometry_from_state(_load_ui_state(), screen.availableGeometry())
    if geometry is None:
        return False
    x, y, _width, _height = geometry
    window.setProperty("x", x)
    window.setProperty("y", y)
    return True

def _place_right(window) -> None:
    """默认贴着屏幕右侧摆。

    原来放在顶部居中，正好压在游戏画面中间，很碍事；靠右放能少挡一大半界面。
    窗口比可用高度还高时，顺手把它压到放得下。
    """
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return
    geo = screen.availableGeometry()

    width = int(window.property("width") or 340)
    height = int(window.property("height") or 700)
    room = geo.height() - 2 * MARGIN
    if height > room:
        height = max(200, room)
        window.setProperty("height", height)

    x = geo.x() + geo.width() - width - MARGIN
    y = geo.y() + MARGIN
    window.setProperty("x", x)
    window.setProperty("y", y)
