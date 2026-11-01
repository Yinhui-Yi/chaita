"""把结构化数据变成界面上给人看的文字。"""

from ..constants import _KEY_LABELS, _ROW_EXTRA_KEYS, _SPECIAL_LABELS


def _split_status(status: dict):
    """把状态拆成三段文本：属性 / 道具 / 金币经验。

    分段依据是玩家的关注顺序：先看血量攻防，再看钥匙和破炸飞，最后看钱和经验。
    层数不在这里显示 —— 地图列表每行就是层数。
    """
    if not isinstance(status, dict):
        return str(status), "", ""

    attr = []
    for key, label in (("hp", "生命"), ("atk", "攻击"),
                       ("def", "防御"), ("mdef", "魔防")):
        value = status.get(key)
        if value is not None:
            attr.append("%s %s" % (label, value))

    items = []
    keys = status.get("keys")
    if isinstance(keys, dict):
        shown = ["%s%d" % (label, keys[key]) for key, label in _KEY_LABELS
                 if isinstance(keys.get(key), (int, float))]
        if shown:
            items.append("钥匙 " + " ".join(shown))
    special = status.get("special")
    if isinstance(special, dict):
        shown = ["%s%d" % (label, special[key]) for key, label in _SPECIAL_LABELS
                 if isinstance(special.get(key), (int, float))]
        if shown:
            items.append(" ".join(shown))

    gold = []
    if status.get("gold") is not None:
        gold.append("金币 %s" % status["gold"])
    if status.get("exp") is not None:
        gold.append("经验 %s" % status["exp"])
    # next 在不同塔里含义不同：有的是升级还需，有的是累计经验
    if status.get("next") is not None:
        gold.append("升级还需 %s" % status["next"])

    return "   ".join(attr), "   ".join(items), "   ".join(gold)

def _carry_row(old, new):
    """重建一行时，把用户自己加的字段从旧行带到新行。"""
    for key in _ROW_EXTRA_KEYS:
        if key in (old or {}) and (key not in new or new.get(key) in (None, "")):
            new[key] = old[key]
    return new

# 地图历史最多保留多少张，避免无限增长
def _floor_text(floor):
    """把模型给的层数整理成可显示的字符串；没读出来就返回空串。

    空串是"这次别记这一层"的信号 —— 地图列表里一条没有层数的记录没有意义。
    """
    if floor is None:
        return ""
    if isinstance(floor, bool):
        return ""
    if isinstance(floor, (int, float)):
        text = str(int(floor)) if float(floor).is_integer() else str(floor)
    else:
        text = str(floor).strip()
    text = _clean_floor_name(text)
    if text.lower() in ("", "null", "none", "未知", "未读层", "?"):
        return ""
    return text


def _clean_floor_name(text: str) -> str:
    """层名只留"字"：头尾的箭头/标点削掉（`"→ 3"` → `"3"`）。

    为什么要有这一条：以前"通到…"那格点开时把**显示文字**（带 "→ "）当成层名
    提交，存档里就多出 `"→ 3"` 这种假层（用户 2026-10-31："楼梯坐标我粘贴后再选中
    楼层信息就没了"）。显示和提交那两处已经修了，这里负责把**旧存档**洗干净。
    只削头尾，中间的字（"通天塔 3"）不动。
    """
    value = str(text or "").strip()

    def _word(ch: str) -> bool:
        return ch.isalnum() or "\u4e00" <= ch <= "\u9fa5"

    head = 0
    while head < len(value) and not _word(value[head]):
        head += 1
    tail = len(value)
    while tail > head and not _word(value[tail - 1]):
        tail -= 1
    return value[head:tail]
