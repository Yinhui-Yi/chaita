"""读一帧游戏画面：切出状态面板与地图，并读出状态数值。

这是整个工具的核心动作，只做三件事：
  1. 抓目标窗口的画面（PrintWindow，不受遮挡）
  2. 按塔描述切出状态面板与地图两块
  3. 把面板交给视觉模型读成结构化数值

不做网格定位、不做逐格识别 —— 那些是另一个需求，当前不需要。

为什么必须把字段清单喂给模型：实测不喂的时候它会编数据 —— 喵塔面板里没有
魔防/经验/金币，模型照样返回了这几个字段。喂上清单并明确"没出现的一律
输出 null"之后，两个塔都读准了。
"""

import base64
import json
import os
import time
from dataclasses import dataclass

import cv2
import numpy as np

from .. import trace
from . import regions as R
from . import towers as tower_mod
from .agent.chat import reply as _chat
from .agent import core as _ai
from .agent.monster import read as _monster
from .agent.map import read as _map
from .towers import Tower

DEFAULT_MAX_TOKENS = 12000


def _config_key() -> str:
    from .. import config
    return config.api_key()


# 请求不设时间上限（用户明确要求：不要超时检查）。
# 实测判类型 1~2 秒，读地图 10~70 秒，读手册 20~70 秒，慢的时候真的超过一分钟；
# 之前按秒数掐断，掐掉的全是"本来能读到"的答案（血瓶、宝石、图标框都这样丢过）。




@dataclass
class Reading:
    """一次读取的结果。"""

    status: dict                 # 结构化状态数值
    map: np.ndarray              # 地图截图（BGR），只用于显示
    name: str = ""               # 塔名，从窗口标题取
    raw: str = ""                # 模型原始输出，读错时便于排查
    kind: str = "status"         # status = 读属性；monsters = 读怪物手册
    monsters: list = None        # kind=monsters 时的怪物列表
    floor: str = ""              # 这次读到的层数（手册画面也能读到）
    items: list = None           # 本层资源（血瓶/宝石）：[{name,effect,count,icon}]
    # 每个格子里有什么（`{"cells": [{row, col, kind, name}]}`）：路线链预填用
    # （docs/ROUTE.md）；行列固定 13×13，AI 读不到内容就是空的
    grid: dict = None

    def __str__(self) -> str:
        if self.kind == "monsters":
            return "Reading(怪物 %d 只)" % len(self.monsters or [])
        return "Reading(状态=%s)" % json.dumps(self.status, ensure_ascii=False)


from .capture import grab as grab_window   # 实现只有一处（截图优先）


def parse_status(raw: str) -> dict:
    """把模型输出解析成 dict。它有时会裹上 markdown 代码块。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return {"_error": "无法解析模型输出", "_raw": raw}


def _ask_model(prompt: str, image=None, api_key: str = None,
               max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """一问一答（无工具、关思考）：给一段提示词和图，拿回文字。

    留给 classify / read_floor / read_status / read_items 这些"看一眼、答一句"的
    老读者；三个功能（手册 / 地图 / 对话）在 `game/agent` 下各有专门实现。
    """
    task = _ai.Task("", lambda text: text, quiet=True)
    return _ai.run(task, prompt, image, api_key=api_key)

def chat(image: np.ndarray, status: dict, message: str, history=None,
         api_key: str = None, tries: int = 2) -> dict:
    """跟玩家聊一句，必要时顺带改记录（对话功能；实现在 game/agent/chat）。

    history 是之前的几轮对话（[{"who":"你"/"AI","text":…}]），模型靠它接住
    "刚才那只怪"这种指代 —— 对话不是一问一答的一次性表单。
    """
    return _chat.reply(image, status, message, history=history,
                       api_key=api_key, tries=tries)

def _classify_prompt() -> str:
    """只判画面类型。故意只要一个词 —— 输出越短，模型越快也越不容易判错。"""
    return (
        "这张魔塔游戏截图的主体是什么？只回一个词，不要解释：\n"
        "map —— 主体是地图（有格子，能看见角色/怪物/物品的摆放）；\n"
        "manual —— 主体是怪物手册/图鉴（一列怪物清单、或某只怪的详情卡）。\n"
        "注意：这个游戏的怪物手册页面**左边仍然显示状态面板**，甚至可以点「返回游戏」，"
        "只要地图被清单/详情卡盖住了，就算 manual。"
    )


def _status_prompt() -> str:
    """地图画面：**只问最关键的那几个字段**。

    实测：这一版（层数/生命/攻防魔防）3.5 秒就能读准；把等级、经验、金币、钥匙、
    破炸飞也一次问上，模型会反复核对思考内容、30 秒都不回来。所以这里只问关键项。
    """
    return (
        "这是魔塔游戏截图。只读左边状态面板，一行 JSON，不要解释：\n"
        '{"floor":"当前层","hp":生命,"atk":攻击,"def":防御,"mdef":魔防}\n'
        "面板上没有的写 null。floor 是「地下30」「通天塔1」「第0层」这类那行，不是 NEXT。"
    )


_ITEM_KINDS = (("药水瓶", "血瓶"), ("宝石", "宝石"))
_ITEM_COLORS = ("红", "蓝", "绿", "黄")


def focus_map(image: np.ndarray, width: int = 800):
    """把地图图缩到指定宽度再送模型。

    实测：整窗图（2582×1390）问"数资源"会 46 秒超时；同一句提示词换成"只裁地图区
    并缩到 800 宽"，16 秒就出结果。整窗里的浏览器标签/地址栏/状态面板是干扰源。
    """
    if image is None or getattr(image, "size", 0) == 0:
        return image
    import cv2

    height, real_width = image.shape[:2]
    if real_width <= width:
        return image
    scale = width / float(real_width)
    return cv2.resize(image, (width, max(1, int(height * scale))),
                      interpolation=cv2.INTER_AREA)


def _items_prompt(kind: str) -> str:
    """一次问一类，颜色固定、答案格式固定 —— 这样模型不会跑偏。

    注意 max_tokens 是"思考 + 正文"共用的：给 2000~4000 时模型想多一点就把预算
    烧光，正文返回空（日志 finish=length, reasoning=4000）。要给足 12000。
    """
    return (
        "这是魔塔地图。只找%s，按颜色分别给出「数量」和「它旁边标的数值」。"
        "一行 JSON，不要解释："
        '{"红":[数量,数值],"蓝":[0,0],"绿":[0,0],"黄":[0,0]}，'
        "没有的颜色写 [0,0]。" % kind
    )


_GEM_ATTRS = {}


def _gem_attr_prompt() -> str:
    """单独、极短地问一句：各色宝石加的是攻击/防御/魔防哪一个。

    为什么拆出来问：把属性塞进"数宝石"那一问里，模型会反复权衡（实测 140 秒
    后宝石那类直接返回空 —— 整类资源丢失）。属性是这座塔的固定常识，问一次就够。
    """
    return (
        "魔塔游戏里，红宝石、蓝宝石、绿宝石、黄宝石分别加的是「攻击」「防御」"
        "「魔防」中的哪一个？只回一行 JSON，不要解释：\n"
        '{"红":"攻击","蓝":"防御","绿":"魔防","黄":"攻击"}'
    )


def read_gem_attributes(api_key: str = None, image=None) -> dict:
    """读各色宝石加什么属性；读过就缓存，避免每次读取都问。"""
    if _GEM_ATTRS:
        return dict(_GEM_ATTRS)
    key = _screen_key(api_key)
    prompt = _gem_attr_prompt()
    text = ""
    for _attempt in range(2):
        text = _ask_model(prompt, image, api_key=key)
        if text.strip():
            break
    parsed = parse_status(text)
    if not isinstance(parsed, dict) or "_error" in parsed:
        trace.note("items.gem_attr_unparsed", raw=str(text)[:120])
        return {}
    attrs = {}
    for color, value in parsed.items():
        if color in _ITEM_COLORS:
            stat = _field_text(value)
            if stat:
                attrs[color] = stat
    _GEM_ATTRS.update(attrs)
    trace.note("items.gem_attr", attrs=attrs)
    return attrs


def _parse_item_schema(text: str, kind: str, kind_label: str,
                       gem_attrs: dict = None) -> list:
    """解析 {"红":[数量, 数值], ...}；宝石的属性来自 read_gem_attributes。"""
    parsed = parse_status(text)
    if not isinstance(parsed, dict) or "_error" in parsed:
        return []
    gem_attrs = gem_attrs or {}
    out = []
    for color, value in parsed.items():
        if color not in _ITEM_COLORS or not isinstance(value, (list, tuple)):
            continue
        if not value:
            continue
        try:
            count = int(value[0])
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        number = _field_text(value[1]) if len(value) > 1 else ""
        if kind == "宝石":
            stat = gem_attrs.get(color, "")
            effect = ("%s+%s" % (stat, number)) if (stat and number) else (
                stat or number)
        else:
            effect = ("回复" + number) if number else ""
        out.append({"name": color + kind_label, "effect": effect,
                    "count": count, "icon": ""})
    return out


def read_items(image: np.ndarray, api_key: str = None) -> list:
    """并行问"药水瓶"和"宝石"，两类都等到有结果为止。

    这里不再设"等多久就放弃"：模型正常作答 15~40 秒，掐断只会白丢结果
    （实测宝石被 20/24 秒掐掉，整类资源消失）。两个线程并行，等它们都结束。

    宝石的属性（攻击/防御/魔防）另外用一个极短的问题问，避免把"数宝石"那一问
    拖垮（实测塞进同一问会 140 秒后整类返回空）。
    """
    import threading

    key = _screen_key(api_key)
    image = focus_map(image, 800)
    box = {}
    gem_attrs = {}

    def ask(kind: str) -> None:
        prompt = _items_prompt(kind)
        text = ""
        # 一次打转（finish=length、正文空）很常见，所以给两次机会；
        # 不设时间上限 —— 想得久就让它想完。
        for attempt in range(2):
            text = _ask_model(prompt, image, api_key=key)
            if text.strip():
                break
        box[kind] = text

    def ask_attrs() -> None:
        nonlocal gem_attrs
        try:
            gem_attrs = read_gem_attributes(api_key=key)
        except Exception as exc:
            trace.note("items.gem_attr_failed", error=repr(exc)[:120])

    threads = []
    for kind, _label in _ITEM_KINDS:
        worker = threading.Thread(target=ask, args=(kind,), daemon=True)
        worker.start()
        threads.append(worker)
    attr_thread = threading.Thread(target=ask_attrs, daemon=True)
    attr_thread.start()

    for worker in threads:
        worker.join()
    attr_thread.join()

    items = []
    for kind, label in _ITEM_KINDS:
        items.extend(_parse_item_schema(box.get(kind, ""), kind, label,
                                        gem_attrs=gem_attrs))
    trace.note("items.collected",
               bottle=bool(box.get("药水瓶", "").strip()),
               gem=bool(box.get("宝石", "").strip()),
               attrs=gem_attrs)
    return _normalize_items(items)


def _floor_prompt() -> str:
    """只问层数。这三个字是整条流程里最先要的：有了层数才知道这条记录属于哪一层。"""
    return (
        "这是魔塔游戏截图。只读左边状态面板最上面那行（例如「地下30」「通天塔1」"
        "「第0层」），一行 JSON，不要解释：\n"
        '{"floor":"当前层"}\n'
        "floor 就是这一行的原文，不是 NEXT；没有就写 null。"
    )


def _status_extra_prompt() -> str:
    """可选的那一半：等级、经验、金币、NEXT、钥匙、破炸飞。读不到不影响关键字段。"""
    return (
        "这是魔塔游戏截图。只读左边状态面板，一行 JSON，不要解释：\n"
        '{"level":等级,"exp":经验,"gold":金币,"next":NEXT,'
        '"keys":{"yellow":0,"blue":0,"red":0,"green":0},'
        '"special":{"po":0,"zha":0,"fei":0}}\n'
        "面板上没有的写 null。"
    )




def _ask(key: str, prompt: str, image: np.ndarray,
         tries: int = 3) -> dict:
    """发请求并解析 JSON。

    两个实测教训：
      · 空正文跟 token 预算大小无关（预算翻倍反而更慢），原样重试更快；
      · 模型偶尔会在思考里打转（finish=length，reasoning 烧到 12000）然后返回空，
        这种一次要 60~110 秒。空就原样重试，但不设时间上限 —— 掐掉只会丢答案。
    """
    raw = ""
    for attempt in range(max(1, tries)):
        budget = DEFAULT_MAX_TOKENS if attempt < 2 else DEFAULT_MAX_TOKENS * 2
        raw = _ask_model(prompt, image, api_key=key, max_tokens=budget)
        if raw.strip():
            break
    parsed = parse_status(raw)
    parsed["_raw"] = raw
    return parsed


def _screen_key(api_key: str = None) -> str:
    key = (api_key or os.environ.get("DEEPSEEK_API_KEY", "") or _config_key())
    if not key:
        raise RuntimeError("缺少 API key：在 config.yaml 填 api_key，"
                           "或设置环境变量 DEEPSEEK_API_KEY")
    return key


def classify(image: np.ndarray, api_key: str = None) -> str:
    """只判画面类型，返回 "manual" 或 "map"。

    单独一次请求，只要一个词：输出短 → 快（约 5 秒）→ 也最不容易判错。
    之前把"判类型 + 读全部内容"塞进一个 JSON，模型偶尔把手册判成地图，
    结果把手册截图当成本层地图存了下来。
    """
    parsed = _ask(_screen_key(api_key), _classify_prompt(), image, tries=2)
    word = str(parsed.get("screen") or parsed.get("_raw") or "").strip().lower()
    return "manual" if "manual" in word else "map"


def read_floor(image: np.ndarray, api_key: str = None) -> str:
    """只读层数（最快的一步，实测 2~4 秒）。"""
    parsed = _ask(_screen_key(api_key), _floor_prompt(), image, tries=2)
    floor = parsed.get("floor")
    if isinstance(floor, str):
        floor = floor.strip()
        if floor.lower() in ("", "null", "none"):
            return ""
        return floor
    return ""


def read_person(image: np.ndarray, api_key: str = None) -> dict:
    """只读人物信息（update 按钮用）：两问**并行**，不碰地图。

    以前是 `thread.start()` 紧跟 `thread.join()` —— 看着并行，其实串着排队，
    实测这个 ↻ 要 25.1 秒（两次模型往返各 ~12 秒）。现在两问各自起线程、一起等。
    """
    import threading

    box = {}

    def _grab_key():
        box["status"] = read_status(image, api_key=api_key)

    def _grab_extra():
        box["extra"] = read_status_extra(image, api_key=api_key)

    workers = [threading.Thread(target=fn, daemon=True)
               for fn in (_grab_key, _grab_extra)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    status = box.get("status")
    if not isinstance(status, dict) or "_error" in status:
        status = {}

    extra = box.get("extra") or {}
    if isinstance(extra, dict):
        for key in ("level", "exp", "gold", "next", "keys", "special"):
            if key in extra and status.get(key) in (None, {}, ""):
                status[key] = extra[key]
    return status


def read_status(image: np.ndarray, api_key: str = None) -> dict:
    """地图画面：只读左边状态面板（短请求，实测 7~11 秒）。"""
    return _ask(_screen_key(api_key), _status_prompt(), image, tries=3)


def read_status_extra(image: np.ndarray, api_key: str = None) -> dict:
    """可选状态（等级/经验/金币/钥匙/破炸飞）。"""
    return _ask(_screen_key(api_key), _status_extra_prompt(), image, tries=1)


def read_manual(image: np.ndarray, api_key: str = None) -> list:
    """读手册：交给 agent 做（官方 Agent + look 工具）。

    实测（`docs/capture/_manual_repro.png`）：18.9 秒，模型自己调 7 次 look，
    五只怪的字段全对，图标 114×115。

    老实现（两次盲问：先问图标框、再问字段，然后按模型给的像素框裁剪）已删除。
    """
    return _monster.read(image, api_key=api_key)


def read_floor_map(image: np.ndarray, api_key: str = None,
                   known=None) -> dict:
    """读这一层的地图：**有哪些怪、各几只 + 有哪些资源**（一次会话读完）。

    界面上的「↻」用它：以前只读怪，资源（血瓶/宝石/钥匙/金币）永远是旧值
    （用户："刷新地图的时候没有更新资源包括宝石血瓶钥匙等"）。
    返回 {"mons": [...], "items": [...], "grid": {"cells": [...]}}，两边的数量都在
    格子角上印的数字里；grid 是"每个格子里有什么"（路线链预填用，读不到就是 {}）。
    """
    if image is None or getattr(image, "size", 0) == 0:
        return {"mons": [], "items": [], "grid": {}}
    data = _map.read(image, api_key=api_key, known=known, with_items=True,
                     with_monsters=True, with_grid=True)
    return {"mons": data.get("mons") or [], "items": data.get("items") or [],
            "grid": data.get("grid") or {}}


def read_floor_monsters(image: np.ndarray, api_key: str = None,
                        known=None) -> list:
    """读这一层的地图：**有哪些怪、各几只**（不要求先给名单）。

    和 read_monster_counts 的分工：那个是给定名字填数字（只能数你已经加过的怪）；
    这个是从图上把出现的怪**列出来**再给数量 —— 界面上「↻」用的就是这个。

    **走 agent**（`agent_read.scan_floor`）：AI 那部分一律用 agent 框架，
    这里只做转发。agent 那边关掉了思考（开着实测 58-130 s），并且允许它用
    look 工具把看不清的地方放大再看。
    """
    if image is None or getattr(image, "size", 0) == 0:
        return []
    return _map.monsters(image, api_key=api_key, known=known)


def _field_text(value) -> str:
    """把字段转成给人看的字符串。

    注意不能写 `value or ""`：防御 0 会被当成"没有"而消失（实测绿头怪防御 0 就丢了）。
    0 是有效数值，只有 None / 空串 / null 才算没有。
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    text = str(value).strip()
    return "" if text.lower() in ("", "null", "none", "无", "?") else text


def _item_icon(name: str) -> str:
    """按"颜色+种类"挑图标名（规则搬到了 iteminfo，这里保留旧名字给老调用点）。

    为什么搬：界面上的「加资源」下拉、地图楼层里的图标都在启动时就要求值，
    而 read.py 顶上带着 cv2/numpy 和整条 AI 链（agent_read → openai，实测
    1.4 秒）。规则放在轻量的 iteminfo 里，界面就不用为了查一张图标去背那 2 秒。
    """
    from . import iteminfo
    return iteminfo.icon_for(name)


def _normalize_items(items) -> list:
    """本层资源：名字 + 效果数值 + 个数 + 图标名。"""
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _field_text(item.get("name"))
        if not name:
            continue
        count = item.get("count")
        if isinstance(count, bool):
            count = None
        elif isinstance(count, str):
            digits = "".join(ch for ch in count if ch.isdigit())
            count = int(digits) if digits else None
        elif not isinstance(count, int):
            count = None
        effect = _field_text(item.get("effect"))
        icon = _item_icon(name)
        if not effect:
            # 画面上没写效果时，按塔的道具表补一个（血瓶 = 体力 +150 这种）
            from . import iteminfo
            effect = iteminfo.effect_for(icon, name)
        out.append({"name": name,
                    "effect": effect,
                    "count": count,
                    "icon": icon})
    return out


def map_snapshot(tower: Tower, image) -> object:
    """只做本地裁图，不调模型。用来"先把地图显示出来"。

    读一次 AI 要十几秒，用户点了读取却什么都不出现体验很差。这一步是纯本地操作，
    毫秒级返回，界面可以先有图，AI 结果到了再补文字。
    """
    if image is None:
        return None
    try:
        _panel_rect, map_rect, cropped = tower_mod.resolve(tower, image)
        # 不再 trim_black：地图区域已经是按画布量出来的方图，
        # 再"裁掉边缘整条黑"会把地图自身的黑色区域吃掉（用户："地图不全"）
        return R.crop(cropped, map_rect)
    except Exception:
        return None


def iteminfo_icon(name: str) -> str:
    """资源名字 → 图标名（红宝石→gem_red）；查不到给空串。"""
    from . import iteminfo
    return iteminfo.icon_for(name)


def read(tower: Tower, api_key: str = None, image=None, screen: str = None,
         on_floor=None, known=None) -> Reading:
    """抓窗口 -> 判画面类型 -> 按类型读内容。

    screen 可以由调用方先判好传进来：界面需要在"判完类型"和"读内容"之间插一步
    （比如先把地图显示出来），否则会重复判一次。传 None 就自己判。
    代码不做任何裁剪假设，换作者、换排版都不用改这里。
    """
    if image is None:
        image = grab_window(tower.process)
    if image is None:
        raise RuntimeError("找不到窗口：进程 %s（游戏没开或已最小化）" % tower.process)

    from . import winutil

    name = winutil.clean_title(winutil.window_title(tower.process)) or tower.name

    if screen is None:
        screen = classify(image, api_key=api_key)
    trace.note("read.classify", name=name, screen=screen)

    if screen == "manual":
        monsters = read_manual(image, api_key=api_key)
        # 手册页只读手册：不读层号、也不回填地图（owner："不要回填！！！"）。
        # 以前这里还会 read_floor() 一次去匹配"当前是第几层"，那又是一次模型往返，
        # 而且层号一读歪就会把怪补到别层上。地图那栏现在只由「读地图」「＋ 加怪」
        # 「↻」和手动编辑来改。
        trace.note("read.manual", count=len(monsters),
                   names=[m.get("name") for m in monsters][:20])
        return Reading(status={}, map=None, name=name, kind="monsters",
                       monsters=monsters)

    # 第二步：状态两问和地图会话**互不依赖**，所以先把它们起上去并行跑。
    # 以前是「地图 → 状态 → 附加字段」串着等，三次模型往返相加（实测 57-70 秒）；
    # 起成线程之后，状态那两问藏在地图会话下面，总时间基本等于最慢那一问。
    import threading

    box = {}
    failure = {}

    def _grab_status():
        try:
            box["status"] = read_status(image, api_key=api_key)
        except Exception as exc:            # 线程里抛异常不会有人接：自己记下来
            failure["status"] = repr(exc)[:200]

    def _grab_status_extra():
        try:
            box["extra"] = read_status_extra(image, api_key=api_key)
        except Exception as exc:
            failure["extra"] = repr(exc)[:200]

    workers = [threading.Thread(target=fn, daemon=True)
               for fn in (_grab_status, _grab_status_extra)]
    for worker in workers:
        worker.start()

    # 第三步：地图画面 —— 一个会话把「层号 / 这层有哪些怪 / 有什么资源」问完。
    # 图只上传这一次；以前是三件事各开一个会话（同一张图发三遍）。
    # try/finally：地图这一问要是抛了，上面两个线程也得收回来，不然它们会继续
    # 在后台跑完、结果掉进已经没人看的 box 里（重试一次就多两个无主请求）。
    try:
        opened = _map.read(image, api_key=api_key, known=known)
    finally:
        for worker in workers:
            worker.join()

    if failure:
        trace.note("read.status_failed", **failure)

    floor = opened.get("floor") or ""
    grid = opened.get("grid") or {}
    map_image = map_snapshot(tower, image)
    trace.note("read.floor", name=name, floor=floor)
    if on_floor is not None:
        try:
            on_floor(floor, map_image)
        except Exception as exc:
            trace.note("read.on_floor_error", error=repr(exc)[:200])

    parsed = box.get("status") or {}
    raw = str(parsed.get("_raw", ""))
    status = parsed
    if not isinstance(status, dict):
        status = {}
    if floor and not str(status.get("floor") or "").strip():
        status["floor"] = floor

    extra = box.get("extra") or {}
    if isinstance(extra, dict):
        for key in ("level", "exp", "gold", "next", "keys", "special"):
            if key not in extra:
                continue
            if status.get(key) in (None, {}, ""):
                status[key] = extra[key]
    trace.note("read.status", name=name, floor=status.get("floor"),
               hp=status.get("hp"), atk=status.get("atk"),
               **{"def": status.get("def"), "mdef": status.get("mdef")},
               keys=bool(status.get("keys")))

    # 怪和资源都来自上面那一个会话；「读怪物」只填"怪物"那一栏，不回填地图。
    monsters = [{"name": row["name"], "count": row["count"]}
                for row in (opened.get("mons") or [])]
    items = [{"name": row["name"], "count": row["count"],
              "icon": iteminfo_icon(row["name"])}
             for row in (opened.get("items") or [])]

    return Reading(status=status, map=map_image, name=name,
                   raw=raw, monsters=monsters, items=items, grid=grid)
