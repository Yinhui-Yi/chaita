"""ReadingMixin：读图/读手册那三件事拼起来（对 Controller 只暴露这一个名字）。

以前还有第四块 `ReadingItemsMixin`（单独再问一次"这层有哪些资源"）：那一问要的是
数量，和现在"清单由格子推、数量 = 占几格"的规则冲突（用户 2026-10-31："AI 现在
不需要读数量"），已经删掉。
"""

from .deliver import ReadingDeliverMixin
from .scan import ReadingScanMixin
from .tasks import ReadingTasksMixin


class ReadingMixin(ReadingTasksMixin, ReadingDeliverMixin, ReadingScanMixin):
    """`controller.py` 的 MRO 里只写 ReadingMixin，内部再分三块。"""
