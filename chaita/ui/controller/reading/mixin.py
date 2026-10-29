"""ReadingMixin：读图/读手册那四件事拼起来（对 Controller 只暴露这一个名字）。"""

from .deliver import ReadingDeliverMixin
from .items import ReadingItemsMixin
from .scan import ReadingScanMixin
from .tasks import ReadingTasksMixin


class ReadingMixin(ReadingTasksMixin, ReadingDeliverMixin,
                   ReadingScanMixin, ReadingItemsMixin):
    """`controller.py` 的 MRO 里只写 ReadingMixin，内部再分四块。"""
