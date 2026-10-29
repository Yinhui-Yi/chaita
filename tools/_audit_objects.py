"""一次性审计脚本：QML 里的 objectName 有哪些从没被任何测试碰过。

用法：
    python tools/_audit_objects.py             # 列出没被碰过的
    python tools/_audit_objects.py --classify  # 再分一下"纯展示"还是"有交互"

分类只是**启发式**：看这个控件自己的块里（往后 40 行）有没有 MouseArea /
onClicked / TextField 之类。它的用处是找出"还没测但确实能点/能改"的控件，
而不是给"没测"找借口 —— 分类结果要自己再看一眼。
"""

import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
QML = ROOT / "chaita" / "ui" / "views"
TESTS = ROOT / "tests"

PATTERN = re.compile(r'objectName:\s*"([A-Za-z0-9_]+)"')
INTERACTIVE = ("MouseArea", "onClicked", "onPressed", "onReleased",
               "TextField", "TextArea", "TextInput", "onEditingFinished",
               "onTextChanged", "onAccepted", "onDropped", "DropArea",
               "onPositionChanged", "Keys.")
DISPLAY_TYPES = ("Text", "Image", "Rectangle", "Item")


def owner_type(lines, index):
    """谁"拥有"这个 objectName：往上找最近的一行 `Xxx {`。"""
    for line_no in range(index, max(-1, index - 12), -1):
        match = re.match(r"\s*([A-Za-z_][\w.]*)\s*\{", lines[line_no])
        if match:
            return match.group(1)
    return "?"


def main() -> int:
    classify = "--classify" in sys.argv
    names = {}
    for path in QML.rglob("*.qml"):
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        for index, line in enumerate(lines):
            for name in PATTERN.findall(line):
                names[name] = (path.name, lines, index)
    text = "\n".join(path.read_text(encoding="utf-8-sig")
                     for path in TESTS.rglob("test_*.py"))
    missing = {n: where for n, where in names.items()
               if ('"%s"' % n) not in text}
    print("QML objectName 总数:", len(names),
          " 测试里**按名字**找过:", len(names) - len(missing),
          " 没被任何测试碰过:", len(missing))
    if not classify:
        for name in sorted(missing):
            print("  %-26s %s" % (name, names[name][0]))
        return 0

    display, hot = [], []
    for name in sorted(missing):
        file_name, lines, index = names[name]
        own = owner_type(lines, index)
        block = "\n".join(lines[index:index + 40])
        hits = [word for word in INTERACTIVE if word in block]
        row = "%s[%s] %s" % (name, own, file_name)
        if own in DISPLAY_TYPES and not hits:
            display.append(row)
        else:
            hot.append(row + "  " + ",".join(hits[:3]))
    print("\n== 显示型（自己的块里没有交互）：%d ==" % len(display))
    for row in display:
        print("  " + row)
    print("\n== 有交互（该看一眼）：%d ==" % len(hot))
    for row in hot:
        print("  " + row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
