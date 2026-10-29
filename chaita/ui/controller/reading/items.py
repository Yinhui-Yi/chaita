"""资源那一趟：单独再问一次模型「这层有哪些资源」，回来合并进那层的 items。

为什么和读图分开：资源和怪是两次请求，谁先回来谁先补，不能整段替换。"""

import time

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from PySide6.QtCore import Slot

from ...constants import MAP_HISTORY_LIMIT, TASK_LIMIT
from ...toolkit.api import _api_key
from ...toolkit.diagnostics import _write_error_log
from ...toolkit.library import _fill_skill_codes, _skill_items_from_text
from ...toolkit.pictures import _save_temp, _save_thumb
from ...toolkit.texts import _carry_row, _floor_text

from ....game import monster_names

from PySide6.QtCore import Slot


class ReadingItemsMixin:
        def _start_items_task(self, game_read, image, key, floor_text,
                              task_id=None) -> None:
            if not floor_text:
                return

            def run():
                from .... import trace
                items = []
                try:
                    items = game_read.read_items(image, api_key=key)
                except Exception as exc:
                    trace.note("items.failed", error=repr(exc)[:160])
                if items:
                    self._post(lambda: self._attach_items(floor_text, items))
                # 资源读完（不管读到没有）才算这次任务真的完成：
                # 之前是主结果一到就打勾，用户看到"打勾了但资源还没出来"。
                self._post(lambda: self._finish_items_task(
                    task_id, floor_text, got_items=bool(items)))

            self._start_thread(run)

        def _finish_items_task(self, task_id, floor_text, got_items=False) -> None:
            if task_id in self._cancelled:
                return
            if got_items:
                self._set_task(task_id, state="done", text=floor_text)
            else:
                # 资源一个都没读到：不打勾，标成失败让用户能重试（右边的「重试」按钮
                # 已经说明了能点它，文案里不用再写"点此重试"）
                self._set_task(task_id, state="failed",
                               text="%s（资源没读到）" % floor_text)

        def _attach_items(self, floor_text, items) -> None:
            """把资源**合并**到对应那层的地图记录上（不新建条目）。

            必须按名字合并，不能整段替换：血瓶和宝石是两次请求，谁先回来谁先补，
            整段替换会让后到的那一类把先到的覆盖掉（实测：宝石把血瓶顶掉了）。
            """
            from .... import trace
            if not items:
                return
            for position, entry in enumerate(self._map_history):
                if entry.get("floor") != floor_text:
                    continue
                updated = dict(entry)
                merged = {item["name"]: item for item in (entry.get("items") or [])}
                for item in items:
                    row = dict(item)
                    # 同名资源再读到一次：别把用户勾过的"拿过了"和换过的图冲掉。
                    # 图标/效果以道具表为准（AI 只给名字和数量）—— 和界面同一套规则，
                    # 落库的时候就填好，session 存下来也是对的。
                    merged[item["name"]] = self._fill_item_display(
                        _carry_row(merged.get(item["name"]), row))
                updated["items"] = list(merged.values())
                self._map_history[position] = updated
                self.mapHistoryChanged.emit()
                trace.note("items.attached", floor=floor_text,
                           added=[i["name"] for i in items], total=len(merged))
                return
