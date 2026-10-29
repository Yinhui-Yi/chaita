"""读取 RMXP 的 .rxdata（Ruby Marshal 格式），取出地图宽高与图块数据。

只实现 Marshal 里实际会出现的类型，够用就行：
  i 整数、: 符号、" 字符串、[ 数组、{ 哈希、T/F 布尔、0 nil、
  u 对象（RMXP 的 RPG::Table / RPG::Map 都是这种）、@ 实例变量、
  f 浮点、/ 正则、; 用户自定义

    python tools/rxdata.py <目录或文件>            # 概览
    python tools/rxdata.py <Map001.rxdata> --dump # 打印结构
"""

import struct
import sys


class Reader:
    def __init__(self, data: bytes) -> None:
        self.d = data
        self.i = 0

    def byte(self) -> int:
        value = self.d[self.i]
        self.i += 1
        return value

    def take(self, n: int) -> bytes:
        chunk = self.d[self.i:self.i + n]
        self.i += n
        return chunk

    def long(self) -> int:
        """Marshal 的变长整数。"""
        b = self.byte()
        if b == 0:
            return 0
        if 1 <= b <= 4:
            value = 0
            for k in range(b):
                value |= self.byte() << (8 * k)
            return value
        if b >= 5:
            # 高位是符号扩展的负数
            value = -1
            for k in range(5 - b if b > 5 else 0):
                value &= ~(0xFF << (8 * k))
            n = b - 5 if b > 5 else 0
            for k in range(n):
                value |= self.byte() << (8 * k)
            return value
        # 负数：b 在 0xFB..0xFF 区间
        n = 0x100 - b
        value = -1
        for k in range(n):
            value &= ~(0xFF << (8 * k))
            value |= self.byte() << (8 * k)
        return value

    def value(self):
        code = chr(self.byte())
        return self._read(code)

    def _read(self, code: str):
        if code == "0":
            return None
        if code == "T":
            return True
        if code == "F":
            return False
        if code == "i":
            return self.long()
        if code == "f":
            return struct.unpack("<d", self.take(8))[0]
        if code == ":":
            return ":" + self.take(self.long()).decode("utf-8", "replace")
        if code == '"':
            return self.take(self.long()).decode("utf-8", "replace")
        if code == "[":
            return [self.value() for _ in range(self.long())]
        if code == "{":
            return {self.value(): self.value() for _ in range(self.long())}
        if code == "u":
            name = self.take(self.long()).decode("utf-8", "replace")
            return {"__class__": name, "__data__": self._ivars()}
        if code == "o":
            # 普通对象：类名 + 实例变量数量 + 变量表。RMXP 的 RPG::Map 走这个。
            name = self.value()
            if isinstance(name, str) and name.startswith(":"):
                name = name[1:]
            return {"__class__": name, "__data__": self._ivars()}
        if code in "IF":
            return self._ivars()
        if code == "l":
            return self.long()
        raise ValueError("未支持的 Marshal 类型 %r（偏移 %d）" % (code, self.i - 1))

    def _ivars(self):
        count = self.long()
        return {self.value(): self.value() for _ in range(count)}


def load(path: str):
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"\x04\x08":
        raise ValueError("不是 Marshal 4.8 数据: %r" % data[:2])
    reader = Reader(data)
    reader.i = 2
    return reader.value()


def describe(value, depth: int = 0, max_depth: int = 3):
    pad = "  " * depth
    if isinstance(value, dict) and "__class__" in value:
        print("%s%s" % (pad, value["__class__"]))
        if depth < max_depth:
            for key, item in value["__data__"].items():
                if isinstance(item, (list, dict)) and len(item) > 12:
                    print("%s  %s: <%s 长度 %d>" % (pad, key, type(item).__name__, len(item)))
                else:
                    print("%s  %s: %r" % (pad, key, item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (list, dict)) and len(item) > 12:
                print("%s%s: <%s 长度 %d>" % (pad, key, type(item).__name__, len(item)))
            else:
                print("%s%s: %r" % (pad, key, item))
    else:
        print("%s%r" % (pad, value))


def main() -> int:
    import glob
    import os

    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    target = sys.argv[1]
    files = sorted(glob.glob(target)) if "*" in target else [target]
    if os.path.isdir(target):
        files = sorted(glob.glob(os.path.join(target, "*.rxdata")))

    for path in files:
        try:
            value = load(path)
        except Exception as exc:
            print("%-24s 读取失败: %s" % (os.path.basename(path), exc))
            continue
        name = os.path.basename(path)
        data = value.get("__data__", value) if isinstance(value, dict) else value
        if isinstance(data, dict) and "width" in data and "height" in data:
            w, h = data["width"], data["height"]
            tiles = data.get("data")
            n = len(tiles) if isinstance(tiles, list) else -1
            print("%-24s 地图 %sx%s  data 长度=%d" % (name, w, h, n))
        else:
            keys = list(data.keys())[:6] if isinstance(data, dict) else type(data).__name__
            print("%-24s %s" % (name, keys))
        if "--dump" in sys.argv:
            describe(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
