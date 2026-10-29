"""完整验收：地图（层数/状态/资源）+ 手册（怪物/图标）+ 怪物数量。

用现场截图跑真实 API，把最终结果打印并落成一张图给用户看。
"""

import os
import sys
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chaita.config import api_key                    # noqa: E402
from chaita.game import read as R                    # noqa: E402
from chaita.game import towers                        # noqa: E402

MAP_SHOT = os.path.join(ROOT, "docs", "capture", "_repro2.png")
MANUAL_SHOT = os.path.join(ROOT, "docs", "capture", "_manual_repro.png")


def main():
    key = api_key()
    tower = towers.H5_MOTA

    print("=" * 60)
    print("① 地图画面：层数 / 状态 / 资源")
    print("=" * 60)
    map_img = cv2.imread(MAP_SHOT)
    floor = R.read_floor(map_img, api_key=key)
    status = R.read_status(map_img, api_key=key)
    print("层数:", floor)
    print("状态:", {k: status.get(k) for k in ("hp", "atk", "def", "mdef")})

    snap = R.map_snapshot(tower, map_img)
    t0 = time.time()
    items = R.read_items(snap, api_key=key)
    print("资源(%.1fs):" % (time.time() - t0))
    for item in items:
        print("   %s  数值=%s  数量=%s  图标=%s" % (
            item["name"], item["effect"] or "-", item["count"], item["icon"]))

    print()
    print("=" * 60)
    print("② 手册画面：怪物 / 图标")
    print("=" * 60)
    manual = cv2.imread(MANUAL_SHOT)
    t0 = time.time()
    monsters = R.read_manual(manual, api_key=key)
    print("手册(%.1fs) 共 %d 只:" % (time.time() - t0, len(monsters)))
    tiles = []
    for index, monster in enumerate(monsters):
        icon = monster.get("icon")
        print("   %d. %-6s 生命=%-8s 攻=%-6s 防=%-6s 状态=%-6s 图标=%s" % (
            index + 1, monster["name"], monster["hp"] or "-", monster["atk"] or "-",
            monster["def"] or "-", monster["status"] or "-",
            "-" if icon is None else "%dx%d" % (icon.shape[1], icon.shape[0])))
        if icon is None:
            continue
        canvas = np.zeros((150, 120, 3), np.uint8)
        h, w = icon.shape[:2]
        scale = min(140 / h, 110 / w)
        resized = cv2.resize(icon, (max(1, int(w * scale)), max(1, int(h * scale))),
                             interpolation=cv2.INTER_AREA)
        canvas[4:4 + resized.shape[0], 4:4 + resized.shape[1]] = resized
        cv2.putText(canvas, str(index + 1), (6, 18), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 255, 255), 1)
        tiles.append(canvas)
    if tiles:
        out = os.path.join(ROOT, "docs", "capture", "_final_icons.png")
        cv2.imwrite(out, np.hstack(tiles))
        print("   图标拼图:", out)

    print()
    print("=" * 60)
    print("③ 怪物数量（拿这层地图问）")
    print("=" * 60)
    names = [m["name"] for m in monsters]
    t0 = time.time()
    counts = R.read_monster_counts(snap, api_key=key, names=names)
    print("数量(%.1fs):" % (time.time() - t0), counts or "（没读到）")

    print()
    print("=" * 60)
    print("汇总")
    print("=" * 60)
    print("层数      :", floor)
    print("人物      : hp=%s atk=%s def=%s mdef=%s" % (
        status.get("hp"), status.get("atk"), status.get("def"), status.get("mdef")))
    print("资源      :", ["%s %s" % (i["name"], i["effect"] or "") for i in items] or "（空）")
    print("怪物(手册):", [m["name"] for m in monsters])
    print("怪物数量  :", counts or "（空）")


if __name__ == "__main__":
    main()
