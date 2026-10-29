"""在真实游戏窗口上验证「底部对话框纠错」这条链路（只读，不写任何记录）。

为什么要单独一个脚本：单元/集成测试里 `chat` 是桩，
证明的只是"我们自己的链路通"。真正没验证过的是最后一环 ——
模型拿到「截图 + 当前状态 JSON + 用户指正」后，是否照指正改、
是否把没提到的字段原样抄回来、reply 是否是一句人话。

`--rounds 2` 还会连发两条指正：第一条改 A 字段，第二条改 B 字段，
然后检查 A 有没有被第二条"改回去"。这正是 `_last_status` 里带着上一次
原始输出（`_raw`）时会出的问题 —— 模型在提示词里同时看到"改后的值"和
"旧文本里的旧值"，容易把旧的抄回来。

跑法：
    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\verify_correction_live.py
    ... --rounds 2
    ... --field hp --value 1234        # 指定第一个要改的字段和值
    ... --message "血量应该是 4321"     # 完全自定义指正内容（单轮）

退出码 0 = 链路可用；1 = 有问题（会打印卡在哪一步）。
"""

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import cv2  # noqa: E402

from chaita.game import read as game_read  # noqa: E402
from chaita.game import towers as tower_mod  # noqa: E402

# 状态里可用来做"改一个数"试验的字段（按优先级）
NUMERIC_FIELDS = ["hp", "atk", "def", "mdef", "money", "exp", "lv"]
# 字段名 → 界面上叫什么，指正的话得说人话
LABEL = {
    "hp": "生命", "atk": "攻击力", "def": "防御力", "mdef": "魔防",
    "money": "金币", "exp": "经验", "lv": "等级",
}


def public(status):
    """去掉内部字段（`_raw` 之类）后的状态，用于"该不该变"的对比。"""
    return {k: v for k, v in (status or {}).items()
            if not str(k).startswith("_")}


def step(text):
    print("\n=== %s ===" % text, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--process", default="msedge.exe")
    parser.add_argument("--field", default="")
    parser.add_argument("--value", type=int, default=0)
    parser.add_argument("--message", default="")
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(ROOT, "logs", "live_correction_" + stamp)
    os.makedirs(folder, exist_ok=True)
    report = {"stamp": stamp, "process": args.process, "rounds": []}
    problems = []

    def save_png(name, image):
        path = os.path.join(folder, name)
        cv2.imwrite(path, image)
        print("  存图：%s (%dx%d)" % (os.path.relpath(path, ROOT),
                                     image.shape[1], image.shape[0]), flush=True)

    step("1. 抓游戏窗口")
    tower = tower_mod.H5_MOTA
    if args.process.lower().startswith("game"):
        tower = tower_mod.RM_TUTORIAL
    began = time.time()
    image = game_read.grab_window(tower.process)
    if image is None:
        print("  抓不到窗口（进程 %s 没有可见窗口）" % tower.process)
        return 1
    print("  抓图 %.1f 秒，%dx%d" % (time.time() - began,
                                     image.shape[1], image.shape[0]), flush=True)
    save_png("window.png", image)

    step("2. 找画布（resolve）")
    panel, map_rect, norm = tower_mod.resolve(tower, image)
    if norm is not image:
        image = norm
    print("  面板 %s  地图 %s" % (panel, map_rect), flush=True)

    step("3. 读一次状态（这就是「读取」那一步）")
    began = time.time()
    status = game_read.read_status(image)
    took = time.time() - began
    if "_error" in status:
        print("  读失败：%s" % status.get("_error"))
        return 1
    print("  %.1f 秒：%s" % (took, json.dumps(status, ensure_ascii=False)),
          flush=True)
    report["read"] = status

    # ---- 组出要改的字段：第一个按参数/优先级挑，第二个换一个 ----
    picks = []
    if args.field:
        picks.append((args.field, args.value or int(status.get(args.field) or 0) + 1))
    for name in NUMERIC_FIELDS:
        if not isinstance(status.get(name), (int, float)):
            continue
        if any(name == picked for picked, _ in picks):
            continue
        if not picks:
            value = args.value or int(status[name]) + 1
        else:
            # 换一个不同的值，避免"本来就是这个数"看不出改没改
            value = int(status[name]) + 7
        picks.append((name, value))
        if len(picks) >= max(1, args.rounds):
            break
    if not picks:
        print("  这次读到的状态里没有可比较的数字字段，没法做对比试验")
        return 1

    current = status
    for index, (field, want) in enumerate(picks, start=1):
        step("4.%d 第 %d 条指正：%s → %d" % (index, index,
                                             LABEL.get(field, field), want))
        if index == 1 and args.message:
            message = args.message
        else:
            message = ("%s这一格读错了，面板上实际是 %d，请改成 %d，其余字段不要动"
                       % (LABEL.get(field, field), want, want))
        print("  指正内容：%s" % message, flush=True)

        before = public(current)
        began = time.time()
        result = game_read.chat(image, current, message)
        took = time.time() - began
        if "_error" in result:
            print("  纠错失败：%s" % result.get("_error"))
            print("  模型原始输出：%r" % str(result.get("_raw", ""))[:400],
                  flush=True)
            problems.append("第 %d 条指正失败：%s" % (index, result.get("_error")))
            break
        fixed = result.get("status") or {}
        reply = result.get("reply") or ""
        print("  %.1f 秒  reply：%s" % (took, reply), flush=True)
        print("  修正后：%s" % json.dumps(fixed, ensure_ascii=False), flush=True)
        report["rounds"].append({"field": field, "want": want, "reply": reply,
                                 "seconds": round(took, 1), "status": fixed,
                                 "raw_returned": "_raw" in fixed,
                                 "stale_raw": (fixed.get("_raw") != current.get("_raw"))
                                 if "_raw" in fixed else None})

        row = public(fixed)
        if not reply.strip():
            problems.append("第 %d 条：reply 是空的" % index)
        if not row:
            problems.append("第 %d 条：没有返回完整 status" % index)
            break
        got = row.get(field)
        same = str(got).strip() == str(want)
        print("  指定字段 %s：要 %r，得 %r → %s"
              % (field, want, got, "对" if same else "不对"), flush=True)
        if not same:
            problems.append("第 %d 条：%s 没改成 %r（实际 %r）"
                            % (index, field, want, got))
        # 之前几轮改对的值必须还在
        for done_field, done_value in picks[:index - 1]:
            now = row.get(done_field)
            kept = str(now).strip() == str(done_value)
            print("  上一条 %s = %r 还在吗：%r → %s"
                  % (done_field, done_value, now, "在" if kept else "被改回去了"),
                  flush=True)
            if not kept:
                problems.append("第 %d 条把上一轮的 %s 改回去了（%r → %r）"
                                % (index, done_field, done_value, now))
        # 没提到的字段必须原样
        for name, value in before.items():
            if name in [picked for picked, _ in picks[:index]]:
                continue
            if str(row.get(name)).strip() != str(value).strip():
                problems.append("第 %d 条：没提到的 %s 被改了（%r → %r）"
                                % (index, name, value, row.get(name)))
        current = fixed

    with open(os.path.join(folder, "report.json"), "w",
              encoding="utf-8") as handle:
        json.dump(report | {"problems": problems}, handle,
                  ensure_ascii=False, indent=2)

    if problems:
        print("\n有问题：", flush=True)
        for text in problems:
            print("  - " + text, flush=True)
    else:
        print("\n链路可用：指正生效、上一轮的值保留、未提到的字段原样、reply 非空。",
              flush=True)
    print("报告：%s" % os.path.relpath(os.path.join(folder, "report.json"), ROOT),
          flush=True)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
