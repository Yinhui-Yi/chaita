"""ChaitaAssistant 悬浮层（门面）。

界面本身的实现在同目录下这几处，这个文件只把名字摆出来：
    qml/MainWindow.qml     界面（QML 单独一份，不再塞进 Python 字符串）
    constants.py            常量与资源路径
    toolkit/            与界面无关的纯函数（桌面 / 素材库 / 截图 / 文本 / 状态 / 日志）
    controller/         控制器（按功能区拆成 mixin，base.py 组装）
    startup.py          启动、收尾、崩溃日志

tests 和 tools 一直按 `overlay.<名字>` 取，所以这里全部保留。`os` 与
`QGuiApplication` 也摆在门面上：测试按 `overlay.os` / `overlay.QGuiApplication`
打桩，打桩会按名字铺到真正持有它的子模块（tests/ui_patch.py）。
"""

import os  # noqa: F401

from . import qt_env  # noqa: F401  (Qt 路径必须先指好)

from PySide6.QtGui import QGuiApplication  # noqa: F401

from .constants import (  # noqa: F401
    APP_TITLE,
    DRAG_INTERVAL_MS,
    HERO_ICON,
    ICON_BASE,
    ITEM_BASE,
    MAP_HISTORY_LIMIT,
    MARGIN,
    MON_DRAG_INTERVAL_MS,
    SESSION_PATH,
    TASK_LIMIT,
    UI_STATE_PATH,
    _ASSETS,
    _BORDER,
    _HTBOTTOM,
    _HTBOTTOMLEFT,
    _HTBOTTOMRIGHT,
    _HTLEFT,
    _HTRIGHT,
    _HTTOP,
    _HTTOPLEFT,
    _HTTOPRIGHT,
    _KEY_LABELS,
    _ROW_EXTRA_KEYS,
    _SESSION,
    _SPECIAL_LABELS,
)
from .controller.controller import Controller  # noqa: F401
from .loader import OVERLAY_QML, QML_DIR, QML_FILE, load_into, qml_url  # noqa: F401
from .startup import (  # noqa: F401
    _enable_crash_log,
    _render_backend_hint,
    _teardown,
    main,
)
from .toolkit.api import _api_key  # noqa: F401
from .toolkit.desktop import NativeHitTest, _cursor_down, _cursor_pos  # noqa: F401
from .toolkit.diagnostics import _write_error_log  # noqa: F401
from .toolkit.library import _import_icon, _load_monster_templates, _load_skill_catalog, _load_templates_from_db, _monster_skill_items, _parse_skill_payload, _skill_items_from_text, _skill_names  # noqa: F401
from .toolkit.pictures import _save_temp, _save_thumb  # noqa: F401
from .toolkit.state import _apply_ui_state, _geometry_from_state, _load_session, _load_ui_state, _place_right, _save_session, _save_ui_state, _session_hint, _ui_state_enabled  # noqa: F401
from .toolkit.texts import _carry_row, _floor_text, _split_status  # noqa: F401


if __name__ == "__main__":
    raise SystemExit(main())
