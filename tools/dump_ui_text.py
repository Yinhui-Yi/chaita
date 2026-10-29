"""把界面里"显示给人看的字"全部列出来，一行一条，方便挑哪些是垃圾。

不渲染、不开窗口：直接从 OVERLAY_QML 里扫静态字符串（text: "..."、
placeholderText: "..."），再加上 Python 侧会写进界面的文案属性。
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chaita.ui import main as ov  # noqa: E402

QML = ov.OVERLAY_QML
LITERAL = re.compile(r'(text|placeholderText|tooltip|title)\s*:\s*"([^"\\]*)"\s*,?\s*$')

print("== QML 里的静态文案（行号: 字段 = 文字） ==")
count = 0
for number, line in enumerate(QML.split("\n"), start=1):
    body = line.split("//")[0].rstrip()
    match = LITERAL.search(body)
    if not match:
        continue
    value = match.group(2).strip()
    if not value:
        continue
    if not re.search(r"[\u4e00-\u9fff]", value):
        continue          # 纯英文/符号的不算"提示"
    count += 1
    print("%5d  %-15s %s" % (number, match.group(1), value))
print("\n共 %d 条中文静态文案" % count)

print("\n== Python 侧会显示出来的文案 ==")
attrs = [name for name in dir(ov) if name.startswith("_STATUS")
         or name in ("APP_TITLE",)]
for name in attrs:
    value = getattr(ov, name)
    if isinstance(value, str):
        print("%-24s %s" % (name, value))
