"""读怪物手册：一个会话，模型读文字 + 给每只怪图标的框；图标由代码按框裁，再抠掉底纹。

两步定位（用户："位置不对，截图不全"）：
  1) 第一次看整张图，读字段，并给每只怪图标的**大概**框 —— 图标只占整图 3% 宽，
     在 2582×1390 的大图上给比例，偏个 1~2%（二三十像素）就切掉一角或带进隔壁
     （样图实测：框只盖住真值的 76%~100%，而且每次读都不一样）。
  2) 代码以每只怪目前最好的框为中心，放宽一圈裁成小图，**一次**发给模型，让它在小图里
     精确框出图标那一整格（连边框）；再以新框为中心用更小的窗口问第二遍。图标在小图里
     占比大得多，位置准得多；代码把小图里的比例换算回整图，再放宽一点点保证怪物不被切，
     裁下来用 rembg 抠掉白边框和底纹（用户："周围的白框太丑了"；没有模型就是截图）。
     框只让它框整格、不让它框"边框里面"：实测后者模型会一会儿框大一会儿只框怪物本身，
     把怪物切掉一块；整格的框稳得多，白边交给抠图去掉。
     模型出错 / 没给可用的框就退回前一遍的结果（最差退回第一步的框，略放宽）。

红线不变：框是模型看着图给的（代码不做识别/测量），代码只做"裁剪 + 抠图"。
"""

import time

from .... import trace
from .. import core
from .. import icons

# 精确定位问几遍：每遍小窗是"目前最好的框"每边放宽这么多倍（第一遍宽、第二遍窄）
REFINE_GROWS = (0.5, 0.3)
# 最终的精确框（整格，连白边）往里收这么多倍：把白边框切掉再抠图。
# 实测整格带着白边框喂给抠图，浅色怪（骷髅人）会被连底纹一起当前景、整块不透明；
# 怪物在格子里四周都留着空，收 6% 切不到它
FINAL_GROW = -0.06
# 精确定位完全没有结果时，退回第一步的框，每边放宽这么多倍（宁可多带一点边）
FALLBACK_GROW = 0.1
# 小图里精确框的宽/高至少占小图的这么多，再小就当模型瞎给
MIN_INNER = 0.15

PROMPT = """你在读一张魔塔游戏的「怪物手册」截图。目标：把每只怪的字段读准，并给出它图标所在那格的框。

两件事：

1) 读字段：name / hp / atk / def / exp / skills。
2) 给每只怪一个 icon_box：这只怪图标所在的那一**整格/整行**在原图上的 0~1 比例
   {x,y,w,h}（x,y 是左上角，w,h 是宽高）。**框整格、松一点没关系**（代码会自己
   把背景抠掉），只要盖住图案、别框到隔壁就行。文字看不清可以用 look 放大看，
   但图标框不用反复调。

只输出一行 JSON，不要解释、不要 markdown：

{"monsters":[{
  "name":"怪物名","hp":"生命","atk":"攻击","def":"防御","exp":"经验",
  "skills":"先攻 连击",
  "icon_box":{"x":0.31,"y":0.42,"w":0.38,"h":0.06}
}]}

规则（**skills 这一条最容易错，重点看**）：
  · **不要输出任何坐标或位置信息以外的字段**，只输出上面这几个字段；
  · 其它一律不要输出（不要加字段、不要写别的数值，例如临界、减伤、1防、
    金币、称号、境界、品阶、能否战斗，全都不需要）；
  · **名字逐字照抄屏幕上那行字**：别按印象补全（"青"不要写成"绿"），
    也不要把别的塔的经典名字套上来；看不清的字照原样留着，不要猜；
  · **skills 只放战斗技能名**（先攻、连击、反击、破防、纳魔为攻这类）。
    手册上那些"剑者""凡阶入门""真仙境九变""领主三阶"是**境界/品阶**，
    **绝对不要**写进 skills —— 用户明确说过不需要境界。没有技能就写空串 ""；
  · 数值原样抄，不要换算、不要补全；看不清就写 ???；
  · hp/atk/def/exp 只放生命/攻击/防御/经验；
  · 按从上到下的顺序列出，不要遗漏。
"""

KEEP = ("name", "hp", "atk", "def", "exp", "skills")


REFINE_PROMPT = """下面按顺序给你 {count} 张小图，每张是怪物手册里**一只怪的图标附近**的截图，依次是：
{names}

请在每张小图里框出**图标那一整格**（带白色边框的方块，把里面的怪连同边框完整框住，
别切掉一角，也别框到旁边的文字或隔壁那格）。框用**这张小图自己**的 0~1 比例
{{x,y,w,h}}（x,y 是左上角，w,h 是宽高）。

只输出一行 JSON，不要解释、不要 markdown：

{{"boxes":[{{"i":1,"x":0.2,"y":0.1,"w":0.5,"h":0.8}}]}}

i 是第几张小图（从 1 数），每张都要给。"""


def _clean_box(value) -> dict:
    """icon_box 只能是 {x,y,w,h} 全在 0~1 的数字，w/h 大于 0；不合法就 {}。"""
    if not isinstance(value, dict):
        return {}
    box = {}
    for key in ("x", "y", "w", "h"):
        try:
            number = float(value.get(key))
        except (TypeError, ValueError):
            return {}
        if not (0.0 <= number <= 1.0):
            return {}
        box[key] = number
    if box.get("w", 0) <= 0 or box.get("h", 0) <= 0:
        return {}
    return box


def _parse(text: str) -> list:
    """模型输出 → 只保留 KEEP 字段 + 校验过的 icon_box（多给的一律丢掉）。"""
    monsters = core.json_object(text).get("monsters")
    if not isinstance(monsters, list):
        return []
    out = []
    for monster in monsters:
        if not isinstance(monster, dict):
            continue
        item = {key: ("" if monster.get(key) is None
                      else str(monster.get(key)).strip()) for key in KEEP}
        item["icon_box"] = _clean_box(monster.get("icon_box"))
        out.append(item)
    return out


def _grown(box: dict, grow: float) -> dict:
    """把框每边放宽 `grow` 倍框宽/框高（夹在 0~1 里；负数 = 往里收）；没有框就返回 {}。"""
    if not box:
        return {}
    left = max(0.0, box["x"] - box["w"] * grow)
    top = max(0.0, box["y"] - box["h"] * grow)
    right = min(1.0, box["x"] + box["w"] * (1 + grow))
    bottom = min(1.0, box["y"] + box["h"] * (1 + grow))
    if right <= left or bottom <= top:
        return {}
    return {"x": left, "y": top, "w": right - left, "h": bottom - top}


def _to_image(window: dict, inner: dict) -> dict:
    """小图里的比例框 → 整图比例框（越出整图的部分夹掉）。"""
    left = window["x"] + inner["x"] * window["w"]
    top = window["y"] + inner["y"] * window["h"]
    width = min(inner["w"] * window["w"], 1.0 - left)
    height = min(inner["h"] * window["h"], 1.0 - top)
    return {"x": left, "y": top, "w": width, "h": height}


def _refine(session, image, names: list, windows: list) -> list:
    """第二步：把每只怪的小窗一次发给模型，换回精确的整图框。

    返回和 `windows` 等长的列表，拿不到可用框的那一项是 {}（调用方退回第一步的框）。
    小窗不合法（没有框 / 裁不出来）的怪不发，也不占序号。模型整个出错同样全部退回 ——
    精确定位是锦上添花，不能让它把读手册拖垮。
    """
    out = [{} for _ in windows]
    todo = []                      # (原序号, 小窗, 小图)
    for index, window in enumerate(windows):
        crop = icons.crop_box(image, window)
        if crop is not None:
            todo.append((index, window, crop))
    if not todo:
        return out
    listing = "\n".join("%d. %s" % (number, names[index] or "（没读到名字）")
                        for number, (index, _w, _c) in enumerate(todo, 1))
    try:
        text, _response = session.ask(
            REFINE_PROMPT.format(count=len(todo), names=listing),
            [crop for _i, _w, crop in todo], label="icon_boxes")
    except Exception as exc:
        trace.note("agent.icon_refine_failed", error=repr(exc)[:200])
        return out
    rows = core.json_object(text).get("boxes")
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            number = int(row.get("i"))
        except (TypeError, ValueError):
            continue
        inner = _clean_box(row)
        if not (1 <= number <= len(todo)) or not inner:
            continue
        if inner["w"] < MIN_INNER or inner["h"] < MIN_INNER:
            continue
        index, window, _crop = todo[number - 1]
        out[index] = _to_image(window, inner)
    return out


def read(image, api_key: str = None) -> list:
    """返回每只怪：name/hp/atk/def/exp/skills/icon（icon 是代码按精确框裁后抠掉底纹的 BGRA）。"""
    if image is None or getattr(image, "size", 0) == 0:
        return []
    started = time.time()
    # 关思考：开着实测 58-135 s；关掉后每轮只要 1-2 s。
    # 只留 look（看小字用，上限 3）；图标框写进 JSON，代码拿到文本后裁小窗、
    # 第二次问模型精确框（一次问完所有怪），再一次裁完。
    with core.Session(PROMPT, tools=(icons.look_tool(image, limit=3),),
                      quiet=True, api_key=api_key) as session:
        text, _response = session.ask("请读这张怪物手册截图。", image,
                                      label="manual")
        monsters = _parse(text)
        if not monsters:
            # 同一次会话里再要一次：历史由 session 维护，不用把图重发一遍
            text, _response = session.ask("请只输出那一行 JSON（monsters 数组）。",
                                          label="manual_retry")
            monsters = _parse(text)
        refined = [{} for _ in monsters]
        rough = [m["icon_box"] for m in monsters]
        names = [m["name"] for m in monsters]
        # 每一遍都以"目前最好的框"为中心裁小窗再问一次：窗口越来越小，
        # 图标在小图里越来越大，误差随之收敛（单遍实测还会偶尔偏出 20+ 像素）
        for grow in REFINE_GROWS if monsters else ():
            best = [exact or box for exact, box in zip(refined, rough)]
            got = _refine(session, image, names,
                          [_grown(box, grow) for box in best])
            refined = [new or old for new, old in zip(got, refined)]
    if not monsters:
        trace.note("agent.manual_empty", raw=text[:200])
        return []
    out = []
    icons_done = 0
    precise = 0
    for item, exact in zip(monsters, refined):
        rough_box = item.pop("icon_box", None)
        # 精确框是整格（连白边）：往里收一点切掉白边，再抠掉底纹
        box = (_grown(exact, FINAL_GROW) if exact
               else _grown(rough_box, FALLBACK_GROW))
        precise += 1 if exact else 0
        item["icon"] = icons.crop_cutout(image, box) if box else None
        if item["icon"] is not None:
            icons_done += 1
        out.append(item)
    trace.note("agent.manual_done", count=len(out), icons=icons_done,
               precise=precise, seconds=round(time.time() - started, 1))
    return out
