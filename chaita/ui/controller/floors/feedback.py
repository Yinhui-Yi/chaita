"""「刚存好」的回执：savedKey 记哪一行，界面让那一格闪绿勾。"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot


class FeedbackMixin:
    @Slot(str)
    def markFloorSaved(self, floor_text) -> None:
        """「完成」按钮的回执：底部那条写一句"已保存"。

        数据其实每格改完就落库了（用户："改完不知道存没存"），所以这里不是真的
        再保存一次，而是给用户一个看得见的结论，并记一条诊断日志。
        """
        from .... import trace
        name = str(floor_text or "").strip()
        if not name:
            return
        self._chat_reply = "已保存「%s」" % name
        self.chatReplyChanged.emit()
        trace.note("manual.floor_saved", floor=name)

    # ---- "已存好了"的回执：改完就落库，但用户看不出到底存没存 ----
    # key 形如 "item:地下30:0" / "mon:地下30:1"，QML 用它让那一格底色闪一下

    def _get_saved_key(self):
        return self._saved_key

    def _mark_saved(self, kind: str, floor_text: str, index) -> None:
        self._saved_key = "%s:%s:%d" % (kind, floor_text, index)
        self.savedKeyChanged.emit()

    def _clear_saved(self) -> None:
        if not self._saved_key:
            return
        self._saved_key = ""
        self.savedKeyChanged.emit()

    # ---- 地图某层的怪物：添加 / 改数量 / 删除 ----
