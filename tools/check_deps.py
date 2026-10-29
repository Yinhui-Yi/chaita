"""查一遍：代码里 import 的第三方包，`environment.yml` 都装了吗。

为什么要有：`agent-framework` 本体只依赖 `agent-framework-core`，
`from agent_framework.openai import OpenAIChatClient` 需要**另外**一个包
`agent-framework-openai`。原 `environment.yml` 只写了 `agent-framework`，
所以照它建出来的新环境一跑「读取」就 ImportError —— 装完等于装不了。

    C:\\Users\\87790\\.conda\\envs\\chaita\\python.exe tools\\check_deps.py
"""

import ast
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 顶层模块名 → 装哪个发行包（pip 名）
PACKAGE_OF = {
    "agent_framework": "agent-framework",
    "openai": "openai",
    "cv2": "opencv",
    "numpy": "numpy",
    "PySide6": "pyside6",
    "win32api": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "win32process": "pywin32",
    "win32ui": "pywin32",
    "pythoncom": "pywin32",
    "dxcam": "dxcam",
    "rembg": "rembg",
    "onnxruntime": "onnxruntime",
}

# 子模块另有发行包的：agent_framework.openai 不在 agent-framework 本体里
SUBMODULE_PACKAGE = {
    ("agent_framework", "openai"): "agent-framework-openai",
}

# 故意可以不在环境里的：没装也能跑（都写在 README「图标」那节）
OPTIONAL = {"rembg", "onnxruntime"}


def imports_of(path: str) -> set:
    """返回 (顶层模块, 子模块) 对；子模块为空串表示只 import 了顶层。"""
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                found.add((parts[0], parts[1] if len(parts) > 1 else ""))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            found.add((parts[0], parts[1] if len(parts) > 1 else ""))
    return found


def environment_packages() -> set:
    path = os.path.join(ROOT, "environment.yml")
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    listed = set()
    in_deps = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("dependencies:"):
            in_deps = True
            continue
        if not in_deps or stripped.startswith("#") or not stripped.startswith("-"):
            continue
        name = re.split(r"[<>=!~ ]", stripped[1:].strip())[0].strip().lower()
        if name and name != "pip:":
            listed.add(name)
    return listed


def main() -> int:
    used = set()
    for base, _dirs, names in os.walk(os.path.join(ROOT, "chaita")):
        for name in names:
            if name.endswith(".py"):
                used |= imports_of(os.path.join(base, name))
    used |= imports_of(os.path.join(ROOT, "run.py"))

    stdlib = set(sys.stdlib_module_names)
    third = {(top, sub) for top, sub in used
             if top not in stdlib and not top.startswith("chaita")}

    listed = environment_packages()
    missing, optional_missing, unknown = [], [], []
    for top, sub in sorted(third):
        package = SUBMODULE_PACKAGE.get((top, sub)) or PACKAGE_OF.get(top)
        if package is None:
            unknown.append("%s.%s" % (top, sub) if sub else top)
            continue
        if package.lower() in listed:
            continue
        label = "%s（import %s%s）" % (package, top, "." + sub if sub else "")
        (optional_missing if top in OPTIONAL else missing).append(label)

    print("第三方导入：%s" % "、".join(sorted(
        "%s.%s" % (t, s) if s else t for t, s in third)))
    print("environment.yml 列出：%s" % "、".join(sorted(listed)))
    if unknown:
        print("!! 认不出对应发行包：%s" % "、".join(sorted(unknown)))
    if optional_missing:
        print("（可选、不列也行）：%s" % "、".join(optional_missing))
    if missing:
        print("!! environment.yml 缺：%s" % "、".join(missing))
        return 1
    print("OK：必需的包都在 environment.yml 里")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
