"""体检 `tools/` 里的脚本：import 还解析得开吗？有没有指向已删模块/路径？

改造过程中删过 `src/`、`agent_read.py`、一堆 overlay 里的函数；工具脚本最容易
悄悄烂在那儿（跑起来才报 ImportError）。这里做静态检查，不执行脚本。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\check_tools.py
"""

import ast
import importlib.util
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, ROOT)

# 已经不存在的模块/名字（历史包袱），出现在 tools 里就是坏引用
GONE_MODULES = {"chaita.game.agent_read", "chaita.ui.main_split"}
GONE_PATHS = ("src/chaita", "src\\chaita")


def module_exists(name: str) -> bool:
    if not name.startswith("chaita"):
        return True
    return importlib.util.find_spec(name) is not None


def main() -> int:
    problems = []
    for name in sorted(os.listdir(TOOLS)):
        if not name.endswith(".py") or name == os.path.basename(__file__):
            continue                      # 检查脚本自己带着"已删模块"常量表
        path = os.path.join(TOOLS, name)
        # utf-8-sig：有些工具脚本是记事本存的，带 BOM（Python 能跑，
        # 但 ast.parse 按 utf-8 读会报 "invalid non-printable character"）
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
        for gone in GONE_MODULES:
            if gone in text:
                problems.append("%s 引用了已删模块 %s" % (name, gone))
        for gone in GONE_PATHS:
            if gone in text:
                problems.append("%s 里还有 %s 这种旧路径" % (name, gone))
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            problems.append("%s 语法错误：%s" % (name, exc))
            continue
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                    and node.module:
                targets = [node.module]
            for target in targets:
                if not module_exists(target):
                    problems.append("%s 导入了不存在的模块 %s" % (name, target))

    total = len([n for n in os.listdir(TOOLS) if n.endswith(".py")])
    print("检查了 %d 个工具脚本" % total)
    if not problems:
        print("OK：没有指向已删模块/旧路径的引用，import 都能解析")
        return 0
    for item in problems:
        print("!!", item)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
