"""「刷新本层」：拿这一层已经存下来的地图截图，问模型「每个格子里有什么」，
再把结果并进记录。

**不问"有哪些怪、各几只 / 有哪些资源"**（用户 2026-10-31："AI 现在不需要读数量"）：
一格一样东西，数格子就是数量 —— 模型自己数的时候经常把格子角上的血量/回血值
当成数量（"1044 只"）。清单里的怪/资源和它们的数量都从格子里数出来。

合并规则不在这儿：`RecordsMixin._merge_read_grid` 一处实现，刷新和「读地图」共用。
"""

from ... import qt_env  # noqa: F401  （Qt 路径必须先指好）

from ...toolkit.api import _api_key


class ReadingScanMixin:
        def _start_scan_task(self, image_url, floor_text, task_id=None) -> None:
            """用那层的地图截图读"每个格子里有什么"，回来并进那一层。

            **不要求先有名单**：以前只能"给定名字填数字"，一层没加过怪就什么都
            做不了（owner：「刷新会读图并统计有哪些怪吗」）—— 现在直接把图上的
            格子列出来，清单和数量都从格子数。
            """
            self._counting_floor = floor_text
            self.countingChanged.emit()

            def done(state, text):
                self._counting_floor = ""
                self.countingChanged.emit()
                if task_id is not None:
                    self._set_task(task_id, state=state, text=text)

            def run():
                from .... import trace
                from ....game import read as game_read
                try:
                    import cv2
                    import numpy as np
                    real = image_url.replace("file:///", "")
                    data = np.fromfile(real, dtype=np.uint8)
                    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
                except Exception as exc:
                    trace.note("scan.load_failed", error=repr(exc)[:120])
                    self._post(lambda: done("failed", "统计失败：截图读不出来"))
                    return
                if image is None:
                    self._post(lambda: done("failed", "统计失败：截图读不出来"))
                    return
                # 手册里的怪名只当"照这个写法写"的提示，不是必须
                known = [str(m.get("name") or "").strip() for m in self._monsters
                         if str(m.get("name") or "").strip()]
                try:
                    data = game_read.read_floor_map(image, api_key=_api_key(),
                                                    known=known)
                except Exception as exc:
                    trace.note("scan.failed", error=repr(exc)[:200])
                    data = {}
                grid = (data or {}).get("grid") or {}
                if grid.get("cells"):
                    self._post(lambda: self._apply_scan(floor_text, grid,
                                                        task_id=task_id))
                else:
                    self._post(lambda: done("failed", "统计失败：没认出格子"))

            self._start_thread(run)

        def _apply_scan(self, floor_text, grid, task_id=None) -> None:
            """把这次读到的「每格有什么」并进那一层。

            规则全在 `_merge_read_grid` 里（一处实现）：用户手动定过的格子/行/楼梯
            一个字段都不动，其余按这次读到的重建，数量 = 它占几格。
            """
            from .... import trace
            if task_id is not None:
                self._counting_floor = ""
                self.countingChanged.emit()
            cells = (grid or {}).get("cells") or []
            for position, entry in enumerate(self._map_history):
                if entry.get("floor") != floor_text:
                    continue
                updated = self._merge_read_grid(entry, grid or {})
                self._map_history[position] = updated
                self.mapHistoryChanged.emit()
                mons = updated.get("mons") or []
                items = updated.get("items") or []
                trace.note("scan.applied", floor=floor_text, cells=len(cells),
                           mons=len(mons), items=len(items))
                if task_id is not None:
                    self._set_task(task_id, state="done",
                                   text="%s：%d 格 · 怪 %d 种 · 资源 %d 种"
                                        % (floor_text, len(cells), len(mons),
                                           len(items)))
                return
            if task_id is not None:
                self._set_task(task_id, state="failed", text="统计失败：这层不见了")
