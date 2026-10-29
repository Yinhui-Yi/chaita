"""一次性审计：745 条测试里哪些"断言不够硬"。

判据（都是这次踩过的坑）：
  1. **一条 assert 都没有** —— 只证明"没抛异常"；
  2. 只有 `is not None` / `is True` 这种空断言 —— 不检查内容；
  3. 在真环境上下手上手（剪贴板 / win32 / 真实文件存在 / 真实时间）却没在这条
     测试里看到对应的 stub —— 结果取决于跑测试那一刻机器状态；
  4. `time.sleep` —— 靠等而不是靠条件。

用法：python tools/_audit_tests.py [名字过滤]
"""

import ast
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# 这些名字出现在测试里，说明它可能直接碰了宿主机
ENV_CALLS = ("windll", "clipboard", "win32api", "win32gui", "GetCursorPos",
             "SetCursorPos", "os.environ", "time.sleep", "GetForegroundWindow")


def tests_in(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            yield node


def source_of(path, node):
    return ast.get_source_segment(path.read_text(encoding="utf-8-sig"),
                                  node) or ""


def _has_raises(node):
    """`with pytest.raises(...)` 也算断言（它就是在断言"这里要抛"）。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "raises":
            return True
    return False


def main() -> int:
    quiet = "--serious" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    needle = args[0] if args else ""
    weak = []
    for path in sorted(TESTS.rglob("test_*.py")):
        for node in tests_in(path):
            text = source_of(path, node)
            asserts = [sub for sub in ast.walk(node)
                       if isinstance(sub, ast.Assert)]
            if not asserts and _has_raises(node):
                continue
            # 空断言：整条 assert 的表达式就是 x is not None / x is True
            weak_only = 0
            for sub in asserts:
                expr = sub.test
                if isinstance(expr, ast.Compare) and len(expr.ops) == 1:
                    op = expr.ops[0]
                    right = expr.comparators[0]
                    if isinstance(op, (ast.IsNot, ast.Is)) and \
                            isinstance(right, ast.Constant) and \
                            right.value in (None, True, False):
                        weak_only += 1
            hits = sorted({call for call in ENV_CALLS if call in text})
            if not asserts:
                weak.append((path, node.name, "没有断言", hits))
            elif weak_only == len(asserts):
                weak.append((path, node.name, "只有空断言(%d 条)" % weak_only,
                             hits))
            elif "time.sleep" in text:
                weak.append((path, node.name, "用了 time.sleep", hits))
            elif hits and "monkeypatch" not in text:
                weak.append((path, node.name, "碰环境但没桩", hits))
    serious = ("没有断言", "time.sleep", "碰环境但没桩")
    for path, name, why, hits in weak:
        if needle and needle not in str(path) + name:
            continue
        if quiet and why not in serious:
            continue
        print("%-58s %-46s %-22s %s" % (path.relative_to(TESTS), name, why,
                                        ",".join(hits)))
    print("\n可疑条数：", len(weak), " / 过滤：", needle or "(全部)",
          " / 只看严重：", quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
