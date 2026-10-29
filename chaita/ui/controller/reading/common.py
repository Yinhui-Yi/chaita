"""读取这一摊共用的小函数（只有一条：数一行记录里有几只）。"""

def _count_of(row) -> int:
    """一行记录里的数量（int），读不出来当 0。合并重复行时比大小用。"""
    try:
        return int((row or {}).get("count") or 0)
    except (TypeError, ValueError):
        return 0
