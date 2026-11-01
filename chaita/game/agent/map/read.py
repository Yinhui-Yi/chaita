"""读地图：一个会话，一张图，问两句——层号 → 每个格子里有什么。

**不再问"这层有哪些怪/资源、各几只"**（用户 2026-10-31："AI 现在不需要读数量"）：
一格一样东西，数格子就是数量，模型只要说清"这一格是什么"就够了。以前那两问
让它数数量，实测经常把血量/效果值（1044、回血 300）当成数量读进来。

为什么是一个会话：层号和格子看的是同一张截图。各开一个会话就是把同一张 2 MB 图
重复上传、重复视觉编码，慢是按调用次数翻倍的（实测 5-6 次调用 = 20-70 秒）。

对外三种用法：
    read(image, api_key)                 一次会话读完两问
                                         → {"floor","grid","mons","items"}
    monsters(image, api_key, known)      只要怪（按格子数出来）
    floor(session) / layout_of(session)  在**已有的会话**里追问（read.read 用这个，
                                         这样一次「读取」只上传一次图）

`grid` 是"每个格子里有什么"（`{"cells": [{row, col, kind, name}]}`）：**它就是唯一
事实来源** —— 清单里的怪/资源和它们的数量都从这儿数出来（`tally`）。行列固定
13×13（用户拍板），不读 AI。
"""

import time

from .... import trace
from .. import core

FLOOR_QUESTION = """你在读魔塔游戏的截图。只回答一件事：现在在**第几层**。
最可能是左边状态面板上的层数文字（例如"地下30""第 12 层""通天塔 5"）。
只回一行 JSON：{"floor":"层数原文"}；看不到就回 {"floor":null}。"""

GRID_QUESTION = """你在读魔塔游戏**这一层的地图**。只回答一件事：**每个格子里有什么**。

读法：
  · 魔塔这一层是 13×13 的格子（**不用你数行列**）；
  · 行从上往下、列从左往右，都从 1 开始（左上角第一格 = 第 1 行第 1 列）；
  · 只记这几类东西：**怪物**（kind = "monster"，名字照它身上的字写）、
    **宝石**（kind = "item"，名字里带"宝石"）、**血瓶药水**（kind = "item"，
    名字里带"血瓶/药水"）、**钥匙**（kind = "item"，黄/蓝/红钥匙）、
    **金币**（kind = "item"）、**武器**（kind = "item"，剑/刀）、
    **防具**（kind = "item"，盾/甲）、**楼梯**（kind = "stair_up" 上楼、
    kind = "stair_down" 下楼，一格就是一级台阶那种图案，一层可能有**好几个**）；
  · 门、地面、地形、NPC 都**不记**；楼梯只记它是哪一格、朝哪边，
    别猜它通到哪一层（那是游戏里的设定，不一定通隔壁层）；
  · **不要写数量**：一格就是一样东西，几格就是几个 —— 别把格子角上的
    血量/回血值当成数量；同一格有两样东西时只记它写的那一个；
  · 一格只记一样；坐标只能在 1~13 之间，看不清的格子跳过，别瞎填。

只回一行 JSON，不要解释：
{"cells":[{"row":3,"col":7,"kind":"monster","name":"红头怪"},
{"row":6,"col":2,"kind":"item","name":"红宝石"},
{"row":8,"col":5,"kind":"item","name":"黄钥匙"},
{"row":12,"col":12,"kind":"stair_up","name":"上楼梯"}]}"""


# 魔塔一层就是 13×13（用户拍板，不读 AI —— 模型数出来 14/15 反而把格子带偏）
SIDE = 13

# 一次最多记多少个"格子有什么"：超了说明模型把整张图都当成了资源
MAX_CELLS = 200

# 格子里记的几类东西：怪 / 可捡的东西（都算 item）/ 上楼梯 / 下楼梯
# （一层可以有好几个楼梯：用户 2026-10-30 "谁告诉你一层只有一个上楼或下楼的"）
CELL_KINDS = ("monster", "item", "stair_up", "stair_down")


def tally(cells, kind: str) -> list:
    """从「每格有什么」数出清单：`[{"name","count"}]`，**数量 = 它占几格**。

    用户 2026-10-31："AI 现在不需要读数量" —— 一格一样东西，数格子就是数量。
    以前那两问让模型自己数，它经常把格子角上的血量/回血值当成数量（"1044 只"），
    或者在"同名多格加起来"时翻倍。数格子这件事不该交给模型。
    """
    order, totals = [], {}
    for cell in cells or []:
        if not isinstance(cell, dict):
            continue
        if str(cell.get("kind") or "") != str(kind or ""):
            continue
        name = str(cell.get("name") or "").strip()
        if not name:
            continue
        if name not in totals:
            order.append(name)
            totals[name] = 0
        totals[name] += 1
    return [{"name": name, "count": totals[name]} for name in order]


def clean_cells(entries) -> list:
    """「每格有什么」：只留怪 / 可捡的东西 / 上楼梯 / 下楼梯，坐标框在 1..13 内（换成 0 开始）。

    AI 报的行列是**从 1 开始**的（人话："第 3 行第 7 列"），这里换成**0 开始**——
    地图层画出来的格子坐标就是 0 开始的，存下来两边才对得上。行列数不读 AI，
    固定 13×13（用户拍板），所以越界的格子（模型数出 14 的时候）直接丢掉。

    资源的**种类不在这里筛**（钥匙、金币、武器、防具都算 item：用户 2026-10-31
    "钥匙/武器/防具也需要记"）—— 清单就是从这些格子数出来的，筛掉哪一类，
    那一类就再也进不了清单。

    楼梯那两类**名字可以空着**（模型只说"这里是一级台阶"），补一个统一的名字；
    通到哪一层模型看不到，留空让人自己选（`stairs` 那摊的事）。
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
        if kind not in CELL_KINDS:
            continue
        if not name:
            if kind == "stair_up":
                name = "上楼梯"
            elif kind == "stair_down":
                name = "下楼梯"
            else:
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


def _known_hint(known) -> str:
    """手册里已经读到的怪名：给模型当"照这个写法写"的提示（不是必须从中挑）。"""
    names = [str(name).strip() for name in (known or []) if str(name).strip()]
    if not names:
        return ""
    # 候选名是"照这个写法写"，不是"必须从中挑一个"：图上明显不是这几只时硬套
    # 候选名会把名字读成另一只怪（用户："哪里来的绿头怪、红头怪"）。
    return ("\n手册里已经读到的怪（**名字照这个写法**）：%s。"
            "图上明显不是其中某一只就照它身上的字写，不要硬套候选名。"
            % "、".join(names[:40]))


def layout_of(session, known=None) -> dict:
    """问"每个格子里有什么"（清单和数量都从它数出来；行列固定 13×13，不读 AI）。"""
    data = core.ask_json(session, GRID_QUESTION + _known_hint(known),
                         label="map_grid")
    return clean_layout(data)


# ---- 对外入口 ----

def _open(image, api_key):
    """开一个会话（图交给第一问带出去，只发这一次）。"""
    from .. import icons
    return core.Session("", tools=(icons.look_tool(image),), quiet=True,
                        api_key=api_key)


def read(image, api_key: str = None, *, known=None) -> dict:
    """一次会话读完：层号 + 每个格子有什么。图只发一次。

    `mons` / `items` 是**从格子里数出来的**（`tally`），不是模型报的：
    一格一样东西，数量 = 它占几格（用户 2026-10-31："AI 现在不需要读数量"）。

    known 是"手册里已经读到的怪名"：只当**候选名字**用（同名不同色、同色不同种
    这类最容易读错），不参与看图。实测同一张地图两次跑，名字会在
    「红史莱姆 / 红头怪」「蓝蝙蝠 / 紫蝙蝠」之间飘；给候选名能让它稳定到手册的写法。
    """
    if image is None or getattr(image, "size", 0) == 0:
        return {"floor": "", "grid": {}, "mons": [], "items": []}
    started = time.time()
    result = {"floor": "", "grid": {}, "mons": [], "items": []}
    with _open(image, api_key) as session:
        result["floor"] = floor(session, image)
        result["grid"] = layout_of(session, known)
    cells = result["grid"].get("cells") or []
    result["mons"] = tally(cells, "monster")
    result["items"] = tally(cells, "item")
    trace.note("agent.map_done", floor=result["floor"],
               mons=len(result["mons"]), items=len(result["items"]),
               cells=len(cells), known=len(list(known or [])),
               seconds=round(time.time() - started, 1))
    return result


def monsters(image, api_key: str = None, known=None, *, quiet: bool = True) -> list:
    """只要"这层有哪些怪、各几只"（「↻」的旧入口；数量同样按格子数）。"""
    if image is None or getattr(image, "size", 0) == 0:
        return []
    started = time.time()
    with _open(image, api_key) as session:
        grid = layout_of(session, known)
    rows = tally(grid.get("cells") or [], "monster")
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
