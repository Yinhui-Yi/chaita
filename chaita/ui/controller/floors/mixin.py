"""FloorsMixin：每层记录 / 资源行 / 这一层的怪 / 路线链 / 格子编辑 / 存好回执。"""

from .feedback import FeedbackMixin
from .grid import GridMixin
from .items import ItemsMixin
from .monsters import FloorMonstersMixin
from .records import RecordsMixin
from .routes import RoutesMixin


class FloorsMixin(RecordsMixin, ItemsMixin, FloorMonstersMixin, RoutesMixin,
                  GridMixin, FeedbackMixin):
    """`controller.py` 的 MRO 里只写 FloorsMixin。"""
