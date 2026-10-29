"""上次退出时留下的那份记录：只在界面上给一句提示，等用户点了才真正加载。

为什么不当启动就恢复：读到的可能是上一次那局（换塔/重开），直接盖上来会让用户
以为界面"自己变了"。所以只给提示，恢复是他的决定。
"""

import os

from PySide6.QtCore import Slot

from ..constants import SESSION_PATH
from ..toolkit.state import _load_session, _save_session, _session_hint


class SessionMixin:
    @Slot()
    def restoreSession(self) -> None:
        """把上次退出时存的层/怪记录读进来（状态面板不恢复，避免旧血量）。"""
        from ... import trace
        data = self._session or _load_session()
        if not data:
            self._session = {}
            self._session_hint = ""
            self.sessionHintChanged.emit()
            return
        monsters = [m for m in (data.get("monsters") or []) if isinstance(m, dict)]
        floors = [f for f in (data.get("floors") or []) if isinstance(f, dict)]
        self._monsters = monsters
        self._map_history = floors
        # 老存档里可能躺着模型自己起的简称（"红史莱姆"）：手册名一到先把它改过来，
        # 否则「怪物」栏会把这些名字当成"手册里没有的怪"另起一行（用户："垃圾词条"）。
        self._align_floor_rows()
        self._session = {}
        self._session_hint = ""
        self.monstersChanged.emit()
        self.mapHistoryChanged.emit()
        self.sessionHintChanged.emit()
        trace.note("session.restored", monsters=len(monsters),
                   floors=len(floors))

    @Slot()
    def discardSession(self) -> None:
        """不要上次的记录：删掉文件，提示消失。"""
        from ... import trace
        self._session = {}
        self._session_hint = ""
        self.sessionHintChanged.emit()
        try:
            os.remove(SESSION_PATH)
        except OSError:
            pass
        trace.note("session.discarded")

    def _get_session_hint(self):
        return self._session_hint


