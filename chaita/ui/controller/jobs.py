"""线程与任务队列：后台怎么跑、结果怎么排回界面线程。

「读取」这类活儿都是网络调用（实测 2~5 秒），必须离开界面线程；而界面状态
（QML 正在读的列表）又不能从后台改 —— 所以只有一条通道：后台算完把"要在界面线程
做的事"丢进 `uiCall`（`_post`），界面线程执行（`_run_ui_call`）。

任务队列是给用户看的：每点一次「读取」一条，跑着的能取消、失败的能重试。
"""

import threading

from PySide6.QtCore import Slot


class JobsMixin:
    def _start_thread(self, target, args=()) -> None:
        """开一个后台线程，并登记下来，退出时能等它们收尾。"""
        if self._closing:
            return
        holder = {}

        def runner():
            try:
                target(*args)
            finally:
                thread = holder.get("thread")
                if thread is not None:
                    try:
                        self._threads.remove(thread)
                    except ValueError:
                        pass

        # 注意：不要在这里用 threading.current_thread() 之类的其它接口 ——
        # 单元测试会把 threading 换成极简替身，只提供 Thread(...)
        thread = threading.Thread(target=runner, daemon=True)
        holder["thread"] = thread
        self._threads.append(thread)
        thread.start()

    @Slot(object)
    def _run_ui_call(self, call) -> None:
        """在界面线程里跑后台线程排过来的活儿。

        后台线程不能直接改 self._map_history 这些 QML 正在读的列表 —— 会读到改到
        一半的中间状态，界面就卡住/错乱。所以后台只算，改状态一律排回主线程。
        """
        try:
            call()
        except Exception as exc:
            from ... import trace
            trace.note("ui.call_error", error=repr(exc)[:200])

    def _post(self, call) -> None:
        """把一个改动界面状态的操作用排回界面线程。"""
        if self._closing:
            return          # 已经在退出：别再去 emit 信号，C++ 那边可能已经销毁了
        self.uiCall.emit(call)

    def _job_done(self) -> None:
        """一个读取任务收尾（在界面线程里跑）。"""
        self._active = max(0, self._active - 1)
        self._reading = self._active > 0
        self.readingChanged.emit()

    def _get_reading(self):
        return self._reading

    # 正在进行的读取任务数：>1 说明并行着几个，按钮上直接显示，点了有反应能看见
    def _get_active_reads(self):
        return self._active

    # ---- 任务队列（技能下面那一栏）----
    def _get_tasks(self):
        return list(self._tasks)

    def _set_task(self, task_id, **fields) -> None:
        """改一条任务的状态并通知界面。"""
        if task_id is None:
            return
        for index, task in enumerate(self._tasks):
            if task.get("id") != task_id:
                continue
            updated = dict(task)
            updated.update(fields)
            self._tasks[index] = updated
            self.tasksChanged.emit()
            return

    def _task_src_path(self, task_id):
        for task in self._tasks:
            if task.get("id") == task_id:
                return task.get("src", "")
        return ""

    def _load_task_src(self, task_id):
        """把任务里存的原图读回来（读不到就返回 None，退回重新抓屏）。"""
        path = self._task_src_path(task_id)
        if not path:
            return None
        try:
            import cv2
            import numpy as np
            real = path.replace("file:///", "")
            data = np.fromfile(real, dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            return image
        except Exception:
            return None

    @Slot(str)
    def log(self, message: str) -> None:
        print("[chaita] " + message, flush=True)
