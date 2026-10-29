"""把 overlay.py 里所有中文短字符串列出来（含注释行），人工过一遍哪些会显示给用户。"""

import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
source = io.open(os.path.join(ROOT, "chaita", "ui", "overlay.py"),
                 encoding="utf-8").read()

pattern = re.compile(r'"([^"\\\n]*[\u4e00-\u9fff][^"\\\n]*)"')
for number, line in enumerate(source.split("\n"), start=1):
    stripped = line.strip()
    if stripped.startswith("#"):
        continue
    for match in pattern.finditer(line):
        print("%5d  %s" % (number, match.group(1)))
