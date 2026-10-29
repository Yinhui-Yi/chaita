"""列一遍"定义了但没人用"的函数（含 Controller 的槽），只报不改。

为什么留着：拆完目录、换过几轮实现之后，最容易留一堆没人调的老函数；这份报告
让"要不要删"变成一次能对账的决定，而不是凭印象。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\dead_code.py
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_GLOBS = ("chaita/**/*.py", "tests/*.py", "tools/*.py")
EXTRA_TEXT = ("chaita/ui/qml/MainWindow.qml",)

DEF = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")


def read(path: str) -> str:
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def main() -> int:
    modules = []
    for pattern in SOURCE_GLOBS:
        for path in __import__("glob").glob(
                os.path.join(ROOT, pattern), recursive=True):
            modules.append(os.path.normpath(path))

    texts = {path: read(path) for path in modules}
    for extra in EXTRA_TEXT:
        path = os.path.normpath(os.path.join(ROOT, extra))
        if os.path.exists(path):
            texts[path] = read(path)

    defs = {}
    for path, text in texts.items():
        if not path.endswith(".py"):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            match = DEF.match(line)
            if match:
                defs.setdefault(match.group(1), []).append((path, number))

    unused = []
    test_only = []
    skip_prefix = ("test_", "setUp", "tearDown", "_test")
    for name, places in sorted(defs.items()):
        if name.startswith("__") and name.endswith("__"):
            continue
        if name.startswith(skip_prefix):
            continue                     # unittest 按名字找这些，不算死代码
        # 用 \bname\b 而不是"前面不能是点"：别的模块是 `capture.find_target(...)`
        # 这样调的，把点排除掉会把活函数报成死函数（第一版就错报了 392 个）。
        pattern = re.compile(r"\b%s\b" % re.escape(name))
        uses = 0
        prod_uses = 0
        for path, text in texts.items():
            # 产品 = chaita/ 下的 .py **和界面 QML**：一堆槽只有 QML 在调
            # （controller.addItem(...)），不算测试
            is_prod = (os.sep + "chaita" + os.sep) in path
            for number, line in enumerate(text.splitlines(), 1):
                if (path, number) in places:
                    continue
                if pattern.search(line):
                    uses += 1
                    if is_prod:
                        prod_uses += 1
                    break
        if uses == 0:
            unused.append((name, places))
        elif prod_uses == 0 and (os.sep + "chaita" + os.sep) in places[0][0]:
            test_only.append((name, places))

    print("定义了但全仓库没有别处引用的函数：%d 个" % len(unused))
    for name, places in unused:
        where = "、".join("%s:%d" % (os.path.relpath(p, ROOT), n)
                         for p, n in places)
        print("  %-28s %s" % (name, where))

    print()
    print("产品代码里没人调用、只有测试/工具在用的函数：%d 个" % len(test_only))
    for name, places in test_only:
        where = "、".join("%s:%d" % (os.path.relpath(p, ROOT), n)
                         for p, n in places)
        print("  %-28s %s" % (name, where))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
