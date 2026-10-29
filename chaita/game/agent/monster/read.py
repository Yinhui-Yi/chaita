"""读怪物手册：一个会话，模型只读文字 + 给每只怪的图标框；图标由代码裁 + 抠（方案 A）。

为什么拆开：以前模型对每只怪调 sprite 工具、还要把抠出来的图回看一遍（配 look），
5 只怪 = 7 次 look + 5 次 sprite ≈ 12 次往返，实测 19~70 秒。现在模型一次看图只回
一行 JSON（字段 + icon_box 文本坐标），代码按框裁 + rembg，模型往返降到 1 次。

红线不变：框还是模型看着图给的（代码不做识别/测量），代码只做允许的"裁剪 + 抠图"。
"""

import time

from .... import trace
from .. import core
from .. import icons

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


def read(image, api_key: str = None) -> list:
    """返回每只怪：name/hp/atk/def/exp/skills/icon（icon 是代码按 icon_box 裁+抠）。"""
    if image is None or getattr(image, "size", 0) == 0:
        return []
    started = time.time()
    # 关思考：开着实测 58-135 s；关掉后每轮只要 1-2 s。
    # 只留 look（看小字用，上限 3）；sprite 工具整个不用了 —— 图标框写进 JSON，
    # 代码拿到文本后一次裁完，模型不再为每只怪多走往返。
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
    if not monsters:
        trace.note("agent.manual_empty", raw=text[:200])
        return []
    out = []
    icons_done = 0
    for item in monsters:
        box = item.pop("icon_box", None)
        item["icon"] = icons.crop_cutout(image, box)
        if item["icon"] is not None:
            icons_done += 1
        out.append(item)
    trace.note("agent.manual_done", count=len(out), icons=icons_done,
               seconds=round(time.time() - started, 1))
    return out
