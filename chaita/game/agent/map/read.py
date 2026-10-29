"""读地图：一个会话，一张图，问四句——层号 → 有哪些怪 → 有什么资源 → 每格有什么。

为什么是一个会话：这四件事看的是同一张截图。各开一个会话就是把同一张 2 MB 图重复
上传、重复视觉编码，慢是按调用次数翻倍的（实测 5-6 次调用 = 20-70 秒）。

对外三种用法：
    read(image, api_key)                 一次会话读完四问
                                         → {"floor","mons","items","grid"}
    monsters(image, api_key, known)      只问怪（「↻」用）
    floor(session) / monsters_of(session) / items(session) / layout_of(session)
                                         在**已有的会话**里追问（read.read 用这个，
                                         这样一次「读取」只上传一次图）

`grid` 是"每个格子里有什么"（`{"cells": [{row, col, kind, name}]}`），路线链预填
用（docs/ROUTE.md）。行列固定 13×13（用户拍板），不读 AI。
"""

import time

from .... import trace
from .. import core

FLOOR_QUESTION = """你在读魔塔游戏的截图。只回答一件事：现在在**第几层**。
最可能是左边状态面板上的层数文字（例如"地下30""第 12 层""通天塔 5"）。
只回一行 JSON：{"floor":"层数原文"}；看不到就回 {"floor":null}。"""

MONSTER_QUESTION = """你在读魔塔游戏**这一层的地图**。只回答一件事：这层出现了哪些怪、各几只。

读法：
  · **数量 = 这一层这种怪有几个**：先数图标的个数（同一只怪摆了几格）；
  · 格子角上如果印着 1~9 那种小数字，也可以当"这一格里有几只"；
  · **三位以上的大数字绝对不是数量** —— 那多半是这一格的怪的血量、临界、或者打它要掉的血
    （实测把 1044 当成"1044 只"）；看到这种就不算它，按图标个数来；
  · 同名怪分散在好几格时，把每格的只数**加起来**；
  · 名字优先用用户给的手册怪名；手册里没有的照它身上的字写，拿不准的不要写；
  · 看不清可以用 look 放大，但**默认别调、最多 3 次**（逐格扫全图要两分钟）。

只回一行 JSON，不要解释：{"monsters":[{"name":"怪名","count":3}]}"""

ITEM_QUESTION = """你在读魔塔游戏**这一层的地图**。只回答一件事：这层地图上有哪些**资源**
（血瓶、宝石，以及钥匙、金币这类可捡的道具）。

读法：
  · 画着道具的格子就是；同名多格把格子上印的数字**加起来**；没有就回空数组；
  · **count 只放"数量"**（格子角上印的那个 1~3 位数，通常 1~9）。血瓶旁边写的
    「回血 300」「体力 1200」那类**是效果数值，不是数量，绝对不要写进 count**；
  · **三位以上的大数字一律不算数量**（那是回血量/效果值）；
  · 看不清可以用 look 放大，但**默认别调、最多 3 次**（逐格扫全图要两分钟）。
只回一行 JSON，不要解释：{"items":[{"name":"红宝石","count":3}]}"""


GRID_QUESTION = """你在读魔塔游戏**这一层的地图**。只回答一件事：**每个格子里有什么**。

读法：
  · 魔塔这一层是 13×13 的格子（**不用你数行列**）；
  · 行从上往下、列从左往右，都从 1 开始（左上角第一格 = 第 1 行第 1 列）；
  · 只记三类东西：**怪物**（kind = "monster"，名字照它身上的字写）、
    **宝石**（kind = "item"，名字里带"宝石"）、**血瓶**（kind = "item"，
    名字里带"血瓶/药水"）；武器、防具、钥匙、门、地面都**不记**；
  · 一格只记一样；坐标只能在 1~13 之间，看不清的格子跳过，别瞎填。

只回一行 JSON，不要解释：
{"cells":[{"row":3,"col":7,"kind":"monster","name":"红头怪"},
{"row":6,"col":2,"kind":"item","name":"红宝石"}]}"""


# 一层里一种东西最多能有几个：超过这个数多半是把血量/效果当成数量读了
# （实测模型把「1044」当"1044 只史莱姆"）。宁可这次不记，也别把离谱数字写进去。
MAX_COUNT = 60

# 魔塔一层就是 13×13（用户拍板，不读 AI —— 模型数出来 14/15 反而把格子带偏）
SIDE = 13

# 一次最多记多少个"格子有什么"：超了说明模型把整张图都当成了资源
MAX_CELLS = 200

# 格子里记的两类东西（门/楼梯/地面不记；门由用户在路线链里点「门」）
CELL_KINDS = ("monster", "item")


def clean(entries) -> list:
    """名字空、数量不是正整数、数量离谱的条目丢掉；同名的合并（数量相加）。"""
    totals, order = {}, []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        try:
            count = int(entry.get("count"))
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        if count > MAX_COUNT:
            from .... import trace
            trace.note("scan.count_absurd", name=name, count=count,
                       limit=MAX_COUNT)
            continue
        if name not in totals:
            order.append(name)
        totals[name] = totals.get(name, 0) + count
    return [{"name": name, "count": totals[name]} for name in order]


def clean_cells(entries) -> list:
    """「每格有什么」：只留怪 / 宝石 / 血瓶，坐标框在 1..13 内（换成 0 开始）。

    AI 报的行列是**从 1 开始**的（人话："第 3 行第 7 列"），这里换成**0 开始**——
    地图层画出来的格子坐标就是 0 开始的，存下来两边才对得上。行列数不读 AI，
    固定 13×13（用户拍板），所以越界的格子（模型数出 14 的时候）直接丢掉。
    """
    out = []
    seen = set()
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        try:
            row = int(str(entry.get("row")).strip())
            col = int(str(entry.get("col")).strip())
        except (TypeError, ValueError):
            continue
        kind = str(entry.get("kind") or "").strip().lower()
        name = str(entry.get("name") or "").strip()
        if kind not in CELL_KINDS or not name:
            continue
        if row < 1 or col < 1 or row > SIDE or col > SIDE:
            continue
        if (row, col) in seen:
            continue                    # 一格只记一样东西：先报的那个算
        seen.add((row, col))
        out.append({"row": row - 1, "col": col - 1,
                    "kind": kind, "name": name})
        if len(out) >= MAX_CELLS:
            break
    return out


def clean_layout(data) -> dict:
    """这一层"每个格子有什么"：`{"cells": [{row, col, kind, name}]}`。

    没有有效格子就回空字典（路线那边一格都不预填）。
    """
    if not isinstance(data, dict):
        return {}
    cells = clean_cells(data.get("cells") or [])
    return {"cells": cells} if cells else {}


# ---- 单问：可以直接喂现成的会话 ----

def floor(session, image=None) -> str:
    """第一问带图："现在第几层" + 图（后面几问只发文字）。"""
    data = core.ask_json(session, FLOOR_QUESTION, image=image,
                         label="map_floor")
    return str(data.get("floor") or "").strip()


def monsters_of(session, known=None, image=None) -> list:
    names = [str(name).strip() for name in (known or []) if str(name).strip()]
    # 候选名是"照这个写法写"，不是"必须从中挑一个"：图上明显不是这几只时硬套
    # 候选名会把名字读成另一只怪（用户："哪里来的绿头怪、红头怪"）。
    hint = (("\n手册里已经读到的怪（**名字照这个写法**）：%s。"
             "图上明显不是其中某一只就照它身上的字写，不要硬套候选名。"
             % "、".join(names[:40])) if names else "")
    if image is not None:
        data = core.ask_json(session, MONSTER_QUESTION + hint, image=image,
                             label="map_mons")
    else:
        data = core.ask_json(session, MONSTER_QUESTION + hint,
                             label="map_mons")
    return clean(data.get("monsters"))


def items_of(session) -> list:
    data = core.ask_json(session, ITEM_QUESTION, label="map_items")
    return clean(data.get("items"))


def layout_of(session) -> dict:
    """最后一问：每个格子里有什么（路线链预填用；行列固定 13×13，不读 AI）。"""
    data = core.ask_json(session, GRID_QUESTION, label="map_grid")
    return clean_layout(data)


# ---- 对外入口 ----

def _open(image, api_key):
    """开一个会话（图交给第一问带出去，只发这一次）。"""
    from .. import icons
    return core.Session("", tools=(icons.look_tool(image),), quiet=True,
                        api_key=api_key)


def read(image, api_key: str = None, *, known=None, with_items: bool = True,
         with_monsters: bool = True, with_grid: bool = True) -> dict:
    """一次会话读完：层号、怪、资源、每个格子有什么。图只发一次。

    known 是"手册里已经读到的怪名"：只当**候选名字**用（同名不同色、同色不同种
    这类最容易读错），不参与看图。实测同一张地图两次跑，名字会在
    「红史莱姆 / 红头怪」「蓝蝙蝠 / 紫蝙蝠」之间飘；给候选名能让它稳定到手册的写法。

    grid 是「路线链」预填要的内容：**每个格子里有什么**（`docs/ROUTE.md`）。
    行列固定 13×13（用户拍板，不读 AI），放在最后问 —— 前面几问的答案先拿到，
    即使这一问失败，怪和资源照样能用。
    """
    if image is None or getattr(image, "size", 0) == 0:
        return {"floor": "", "mons": [], "items": [], "grid": {}}
    started = time.time()
    result = {"floor": "", "mons": [], "items": [], "grid": {}}
    with _open(image, api_key) as session:
        result["floor"] = floor(session, image)
        if with_monsters:
            result["mons"] = monsters_of(session, known)
        if with_items:
            result["items"] = items_of(session)
        if with_grid:
            result["grid"] = layout_of(session)
    trace.note("agent.map_done", floor=result["floor"],
               mons=len(result["mons"]), items=len(result["items"]),
               cells=len(result["grid"].get("cells") or []),
               known=len(list(known or [])),
               seconds=round(time.time() - started, 1))
    return result


def monsters(image, api_key: str = None, known=None, *, quiet: bool = True) -> list:
    """只问"这层有哪些怪"（「↻」用；不需要层号和资源）。"""
    if image is None or getattr(image, "size", 0) == 0:
        return []
    started = time.time()
    with _open(image, api_key) as session:
        rows = monsters_of(session, known, image=image)
    trace.note("agent.map_mons", count=len(rows), known=len(list(known or [])),
               seconds=round(time.time() - started, 1))
    return rows


def classify(image, api_key: str = None) -> str:
    """这是地图还是怪物手册？只给「读取」用来防错，不作为独立功能暴露。"""
    if image is None or getattr(image, "size", 0) == 0:
        return ""
    doc = ("你在看一张魔塔游戏的截图。只回答一件事：这是**地图**画面还是"
           "**怪物手册/图鉴**？只回 {\"screen\":\"map\"} 或 "
           "{\"screen\":\"manual\"}，不要解释。")
    answer = core.run(
        core.Task(doc, lambda text: core.json_object(text).get("screen") or "",
                  quiet=True),
        "这是地图还是怪物手册？", image, api_key=api_key)
    return answer if answer in ("map", "manual") else ""
