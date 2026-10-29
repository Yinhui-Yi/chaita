"""MonstersMixin：怪物记录 / 图标 / 增删改 / 拖动排序（名字不变）。"""

from .drag import DragMixin
from .edit import EditMixin
from .icons import IconsMixin
from .read import ReadMixin


class MonstersMixin(ReadMixin, IconsMixin, EditMixin, DragMixin):
    """`controller.py` 的 MRO 里只写 MonstersMixin。"""
