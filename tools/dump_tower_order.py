"""把两座塔 `project/enemys.js` 里怪物的排列顺序抄成 `library.TOWER_ORDER`。

用户："不同种类的顺序说了按同类里最弱的排你排了吗？蝙蝠怎么这么靠后" ——
素材库按"类"排的时候，类的先后用塔里怪物的先后（作者就是按关卡/强弱排的）：
史莱姆 → 蝙蝠 → 骷髅 → 丧尸 → 石怪 → 法师 → 守卫 → 骑士 → 魔王 → 龙 …

用法：
    python tools/dump_tower_order.py          # 打印列表（贴回 chaita/library.py）
    python tools/dump_tower_order.py --check  # 只对比库里的表对不对
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chaita import library                            # noqa: E402

HOME = os.path.expanduser("~")
TOWERS = [
    os.path.join(HOME, "Downloads", "xinxin2new", "xinxin2",
                 "project", "enemys.js"),
    os.path.join(HOME, "Downloads", "xinxin", "mota_pack_20260623_204744",
                 "project", "enemys.js"),
]

# enemys.js 里每只怪一行：`"greenSlime": {"name":"…","hp":35,…},`
_KEY = re.compile(r'^\s*"(\w+)"\s*:\s*\{', re.M)


def read_order(path):
    if not os.path.exists(path):
        print("读不到：%s" % path)
        return []
    text = io.open(path, encoding="utf-8", errors="replace").read()
    return _KEY.findall(text)


def main(argv):
    combined = []
    for path in TOWERS:
        for key in read_order(path):
            if key not in combined:
                combined.append(key)
    if not combined:
        print("两座塔的 enemys.js 都没找到（先确认 Downloads 里那两个文件夹）")
        return 1
    if "--check" in argv[1:]:
        if combined == list(library.TOWER_ORDER):
            print("一致：%d 个贴图键" % len(combined))
            return 0
        only_file = [key for key in combined
                     if key not in library.TOWER_ORDER]
        only_code = [key for key in library.TOWER_ORDER
                     if key not in combined]
        print("不一致：文件里多 %r，代码里多 %r" % (only_file, only_code))
        return 1
    lines = []
    row = "    "
    for key in combined:
        piece = '"%s", ' % key
        if len(row) + len(piece) > 78:
            lines.append(row.rstrip())
            row = "    "
        row += piece
    lines.append(row.rstrip().rstrip(","))
    print("TOWER_ORDER = [")
    print("\n".join(lines))
    print("]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
