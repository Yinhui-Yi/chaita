"""界面层。

Qt 的 DLL 与 QML 模块都在 conda 环境的 Library 下，而 PySide6 包里没有
qt.conf，所以路径必须在**任何模块 import PySide6 之前**指好，否则
QML 加载会报「找不到 qtquick2plugin.dll」。放在包初始化里，谁先导入
这个包都先经过这里。
"""

import os
import sys

_LIBRARY = os.path.join(sys.prefix, "Library")

os.environ["PATH"] = os.pathsep.join(
    [os.path.join(_LIBRARY, "bin"), os.environ.get("PATH", "")])
os.environ.setdefault("QML2_IMPORT_PATH",
                      os.path.join(_LIBRARY, "lib", "qt6", "qml"))
os.environ.setdefault("QT_PLUGIN_PATH",
                      os.path.join(_LIBRARY, "plugins"))
