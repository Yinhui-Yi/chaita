"""把"图上读到的怪名"对到"手册里读到的怪名"上。

为什么需要：地图上没有怪物名，只有图案 —— 读地图时模型是**看图案猜名字**，
它会挑一个自己熟悉的叫法（经典样板塔的「绿头怪 / 红头怪」就是这么冒出来的），
而手册里明明已经写着这只怪叫什么。用户："哪里来的绿头怪、红头怪"、
"刷新地图的时候不看已经读的怪物的？"

做法只到**字符串**这一层，不做任何图像判断：
  · 一模一样（去掉空格/标点后）→ 用它；
  · 否则取"和手册名最像的那个"，但必须**唯一最像**且至少共两个字，
    像"绿头怪"对"青头怪"（共同"头怪"）这种才认；
  · 两个手册名一样像（"红色史莱姆"/"绿色史莱姆"对"史莱姆"）就当没对上 ——
    宁可漏一只，也不要把名字记错。
"""

import re

_STRIP = re.compile(r"[\s·・,，。.、/\\/（）()\[\]【】\"'“”‘’!！?？~～-]+")


def normalize(name) -> str:
    """去掉空白/标点，统一小写。"""
    return _STRIP.sub("", str(name or "")).lower()


def _lcs(left: str, right: str) -> int:
    """最长公共子串的长度（名字都很短，直接 DP）。"""
    if not left or not right:
        return 0
    best = 0
    previous = [0] * (len(right) + 1)
    for i in range(len(left)):
        current = [0] * (len(right) + 1)
        for j in range(len(right)):
            if left[i] == right[j]:
                current[j + 1] = previous[j] + 1
                if current[j + 1] > best:
                    best = current[j + 1]
        previous = current
    return best


def _is_subsequence(short: str, long: str) -> bool:
    """short 的每个字是不是按顺序出现在 long 里（"红史莱姆" ⊂ "红色史莱姆"）。"""
    if not short or len(short) > len(long):
        return False
    rest = iter(long)
    return all(char in rest for char in short)


def match_one(name: str, known, strict: bool = False) -> str:
    """给一个读到的名字，在手册名里找最像的那个；找不到/不唯一返回 ""。

    `strict=True`：只认"一模一样"或"是某个手册名的缩写（子序列）"，不做
    "最像的那个"那一步。**读手册的时候必须用这个** —— 手册页上的名字是印着的
    真名，"小蝙蝠"和"大蝙蝠"这种共两个字的不同怪，用"最像"会被判成同一只，
    结果读了两只只记一只（用户："读取记录显示读取两只但看怪物只有一只"）。
    """
    target = normalize(name)
    if not target:
        return ""
    pool = [str(candidate or "").strip() for candidate in (known or [])
            if str(candidate or "").strip()]
    for text in pool:
        if normalize(text) == target:
            return text                    # 一模一样，直接用
    # 少一个字的名字（"红史莱姆" = "红色史莱姆"）：只判"是不是某个候选的子序列"。
    # 不能只靠最长公共子串 —— "红史莱姆" 和"红色史莱姆"/"绿色史莱姆"都共有"史莱姆"，
    # 分数一样 → 判成"对不上" → 这只怪被丢掉、刷新再也不更新它的数量
    # （用户："刷新第0层…出现了垃圾词条"就是这么来的）。
    supers = [text for text in pool
              if _is_subsequence(target, normalize(text))]
    if strict:
        # 严格模式（读手册用）：只认"中间少了个修饰字"的缩写 ——
        # 「红史莱姆」⊂「红色史莱姆」（首字红、尾字姆都对得上）算同一只；
        # 「血蚊」→「血蚊王」尾巴变长了、首字又不同的，都是**别的怪**，不许并。
        kept = [text for text in supers
                if target[0] == normalize(text)[0]
                and target[-1] == normalize(text)[-1]]
        return kept[0] if len(kept) == 1 else ""
    if len(supers) == 1:
        return supers[0]
    # 好几个候选都装得下（"史莱姆"）→ 只能退回"最像的"，还是一样像就当没对上
    best_name = ""
    best_score = 0
    tie = False
    for text in pool:
        score = _lcs(target, normalize(text))
        if score < 2:
            continue
        if score > best_score:
            best_score = score
            best_name = text
            tie = False
        elif score == best_score:
            tie = True
    return "" if tie else best_name


def align(names, known) -> tuple:
    """把一批读到的名字对到手册写法上。

    返回 (mapping, unmatched, invented)：
      mapping —— 读到名 → 手册名（**只在两者不一样时**才出现）；
      unmatched —— 手册里没有对应、且和哪个都不像的名字（调用方决定丢不丢）；
      invented —— 有候选但唯一对上的那些（用于日志）。
    """
    mapping = {}
    unmatched = []
    invented = []
    pool = [str(name or "").strip() for name in (known or [])
            if str(name or "").strip()]
    for name in names or []:
        text = str(name or "").strip()
        if not text or text in mapping:
            continue
        found = match_one(text, pool)
        if not found:
            unmatched.append(text)
            continue
        # 只差空格/标点的算"本来就一样"，不要记成一次改名
        if normalize(found) != normalize(text):
            mapping[text] = found
            invented.append(text)
    return mapping, unmatched, invented
