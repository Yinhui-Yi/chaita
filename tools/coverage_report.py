"""用标准库 trace 跑一遍测试，统计 chaita/ 的行覆盖率（不依赖 coverage 包）。

用法：
    python tools/coverage_report.py
"""

import ast
import io
import os
import runpy
import sys
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 只看产品代码。以前 SRC = ROOT，连 logs/ 里的旧备份（6000+ 行）都进了分母，
# 覆盖率被稀释成 6.8%（实测）。
SRC = os.path.join(ROOT, "chaita")
TESTS = os.path.join(ROOT, "tests")

EXCLUDE_DIRS = (os.sep + "game" + os.sep + "rxdata",)


def statement_lines(path):
    """用 AST 收集"可执行语句"的行号（跳过 docstring）。"""
    try:
        tree = ast.parse(io.open(path, encoding="utf-8").read())
    except Exception:
        return set()
    lines = set()
    docstring_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno)
            docstring_lines.update(range(start, end + 1))
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not isinstance(node, ast.Expr):
            if getattr(node, "lineno", None):
                lines.add(node.lineno)
    return lines - docstring_lines


def collect_files():
    files = []
    for base, _dirs, names in os.walk(SRC):
        if any(excluded in base for excluded in EXCLUDE_DIRS):
            continue
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(base, name))
    return files


def main():
    files = collect_files()
    statements = {path: statement_lines(path) for path in files}
    hit = {path: set() for path in files}
    targets = set(files)

    def tracer(frame, event, arg):
        filename = frame.f_code.co_filename
        if filename not in targets:
            return None
        if event == "line":
            hit[filename].add(frame.f_lineno)
        return tracer

    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    # 注意：tracing 必须在 discover 之前装上。测试模块 import 的一瞬间就会
    # import chaita 里的模块，模块级语句（import、常量、函数定义、dataclass
    # 构造）确实执行了，coverage 包也把它们算作已覆盖。装晚了这些行全会记成
    # "没覆盖"，覆盖率被凭空拉低十几个点，测的人会去追根本不存在的洞。
    sys.settrace(tracer)
    threading.settrace(tracer)
    try:
        loader = unittest.TestLoader()
        suite = loader.discover(TESTS)
        result = unittest.TextTestRunner(verbosity=0).run(suite)
    finally:
        sys.settrace(None)
        threading.settrace(None)

    total_stmt = sum(len(lines) for lines in statements.values())
    total_hit = sum(len(hit[path] & statements[path]) for path in files)

    rows = []
    for path in files:
        lines = statements[path]
        if not lines:
            continue
        covered = len(hit[path] & lines)
        rows.append((covered / len(lines), covered, len(lines),
                     os.path.relpath(path, ROOT)))
    rows.sort()

    print("=" * 78)
    print("%-52s %6s %6s %7s" % ("文件", "覆盖", "语句", "覆盖率"))
    print("-" * 78)
    for ratio, covered, lines, name in rows:
        if ratio < 0.5:
            print("%-52s %6d %6d %6.1f%%" % (name, covered, lines, ratio * 100))
    print("-" * 78)
    for ratio, covered, lines, name in rows:
        if ratio >= 0.5:
            print("%-52s %6d %6d %6.1f%%" % (name, covered, lines, ratio * 100))
    print("=" * 78)
    print("总计：%d/%d 行，覆盖率 %.1f%%" % (
        total_hit, total_stmt, 100.0 * total_hit / max(1, total_stmt)))
    print("测试结果：", "通过" if result.wasSuccessful() else "失败")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
