"""把 preview_overlay 的每个场景都渲染一遍，检查三件事：

1. 有没有 QML 运行期警告（"Unable to assign"、"TypeError"、"is not defined" 之类）——
   这些在截图里看不出来，但都是界面接错了；
2. 图是不是空的（全黑/全透明），且**尺寸是不是要的那个**（v12 之后窗口高度由内容
   撑出来，所以这里按场景记一个逻辑高度：内容变了高度就该变，这里等于把"变没变对"
   钉住）；
3. 渲染进程有没有正常退出。

失败了会重跑一次：偶发的"这一帧还没画出来"不该报成界面坏了。

用法：
    python tools/check_scenarios.py            # 跑全部
    python tools/check_scenarios.py empty long # 只跑指定的
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
PREVIEW = os.path.join(ROOT, "tools", "preview_overlay.py")
OUT_DIR = os.path.join(ROOT, "logs", "_scenarios")

# (场景, 期望的逻辑高度)。高度是内容撑出来的，改布局就会变 —— 变了就跟着改这里。
SCENARIOS = [
    ("default", 657),
    ("empty", 296),
    # long / error / session / queue 会被"屏幕高 72%"封顶（这台屏幕 912 高）
    ("long", 657),
    ("reading", 657),
    ("error", 657),
    ("collapsed", 102),
    # 什么都没读到又收起时：只剩导航条一条（46）
    ("collapsed-empty", 46),
    ("session", 657),
    # 地图的子界面 / 怪物编辑界面（都是满窗覆盖，高度跟主界面一样）
    # 地图搬进 map_view/MapWindow.qml 之后，「这一层」小窗只剩清单（比主窗口矮），
    # 拼图高度就是主窗口的 657；大图那扇窗（map/mapedit/mapstairs）同理。
    ("floor", 657),
    # 清单滚到资源那一段（看资源行）
    ("flooritems", 657),
    # 小窗拉矮时，加资源的下拉菜单要完整显示
    ("floorsmall", 657),
    # 地图那一栏：侧栏切层 + 单层大图 / 编辑模式 + 标楼梯 / 标好的楼梯 / 多张叠放
    ("map", 657),
    ("mapedit", 657),
    ("mapstairs", 657),
    ("mapstack", 657),
    # 路线对比 + 点一行去地图上圈格
    ("compare", 657),
    ("comparehi", 657),
    # 地图/怪物两栏都折叠：窗口跟着变矮（657 → 438；造景只有一层地图，比
    # 以前两层的造型矮一点）
    ("folded", 438),
    # 加怪是挂在「＋」下面的下拉菜单（不是整页覆盖）
    ("floorpick", 657),
    ("monedit", 657),
    # 技能参数里的开关 / 二选一（吸血、领域）
    ("monparams", 657),
    # 自定义技能：名称 + 自己写的介绍
    ("moncustom", 657),
    # 伤害计算：一行一条链（勇者 → 怪 → 宝石 → 怪），掉血写在怪后面
    ("battle", 657),
    # 还没点「计算」：每格"—"，底下一个「计算」按钮
    ("battleplan", 657),
    # 两行不同顺序摆一起，右边总掉血对着比（用户："怎么对比不同排序的掉血"）
    ("battlecmp", 657),
    # 点链上的箭头：菜单写"插在第 k 格前面"（用户："点箭头要能插入"）
    ("battleinsert", 657),
    # 问号菜单的「资源」页：只有两个标签页，资源里带 4 色宝石
    ("battlepick", 657),
    # 点缩略图改参数（技能参数也能改）
    ("battleedit", 657),
    # 对话：只留一问一答，长回答折行
    ("chatlong", 657),
    # 素材库搜索（图片 + 名字 + 搜索）
    ("iconsearch", 657),
    # 并行读取：两条在跑、一条失败、一条成功
    ("iconpick", 657),
    ("queue", 657),
]

WARN = re.compile(
    r"Unable to assign|TypeError|ReferenceError|is not defined"
    r"|Cannot read property|Cannot call method|Binding loop"
    r"|Cannot assign to non-existent", re.I)


def png_size(path):
    """读 PNG 头里的宽高（不依赖 PIL）。"""
    try:
        with open(path, "rb") as handle:
            head = handle.read(33)
    except OSError:
        return 0, 0
    if head[:8] != b"\x89PNG\r\n\x1a\n" or len(head) < 24:
        return 0, 0
    return (int.from_bytes(head[16:20], "big"),
            int.from_bytes(head[20:24], "big"))


def render_once(name, logical_height, out):
    """渲染一次，返回 (状态, 尺寸, 大小, 警告列表)。"""
    if os.path.exists(out):
        os.remove(out)      # 先删旧图：渲染失败时别拿上一次的图冒充
    proc = subprocess.run(
        [PY, PREVIEW, out, "0", name],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=ROOT)
    text = (proc.stdout or "") + (proc.stderr or "")
    warnings = [line.strip() for line in text.splitlines()
                if WARN.search(line)]
    if proc.returncode != 0 and not warnings:
        tail = (text.strip().splitlines() or [""])[-1]
        warnings.append("进程退出码 %d：%s" % (proc.returncode, tail[:120]))
    size = os.path.getsize(out) if os.path.exists(out) else 0
    width, height_px = png_size(out)
    # DPR 用预览脚本自己打的那行 "dpr 1.500"：有些场景（伤害计算）拼出来的图
    # 比主窗口宽，拿宽度反推会算错
    dpr = 0.0
    found = re.search(r"dpr ([\d.]+)", text or "")
    if found:
        try:
            dpr = float(found.group(1))
        except ValueError:
            dpr = 0.0
    if not dpr:
        dpr = width / 340.0 if width else 0
    want = logical_height * dpr if dpr else 0
    size_ok = bool(width) and abs(height_px - want) <= 4
    ok = not warnings and size >= 2000 and size_ok
    return ("OK" if ok else "BAD"), (width, height_px, want), size, warnings


def main(argv):
    picked = set(argv[1:])
    os.makedirs(OUT_DIR, exist_ok=True)
    bad = []
    for name, height in SCENARIOS:
        if picked and name not in picked:
            continue
        out = os.path.join(OUT_DIR, name + ".png")
        state, dims, size, warnings = render_once(name, height, out)
        if state == "BAD":
            # 偶发的"这一帧还没画出来"重跑一次，别误报界面坏了
            state, dims, size, warnings = render_once(name, height, out)
        width, height_px, want = dims
        print("%-12s %-4s size=%7d %4dx%-4d want_h=%.0f warnings=%d"
              % (name, state, size, width, height_px, want, len(warnings)))
        for line in warnings[:3]:
            print("      " + line[:140])
        if state == "BAD":
            bad.append(name)
    print("\n结果:", "全部干净" if not bad else ("有问题：" + ", ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
