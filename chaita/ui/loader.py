"""QML 加载器：读整棵树的 QML + 按磁盘路径装进引擎。**不放在 `qml/` 里**。

`qml/` 是资源目录（只放 .qml 和 qmldir）。把 Python 塞进去，
"哪份是代码、哪份是界面"就分不清了（用户："文件夹结构、文件名都让人困惑"）。

    chaita/ui/
        loader.py                  ← 这个文件（Python）
        qml/                       只放界面：一层 UI 一个文件夹，子界面套在子文件夹里
            MainWindow.qml              第 1 层：主窗口（导航条 / 三栏 / 对话 / 放大看图）
            components/                 到处都要用的小件 + 配色
                FlatBtn.qml                 扁按钮
                Theme.qml                   配色和字体（单例，qmldir 注册）
                qmldir
            windows/                    第 2 层：另开的窗口（子界面）
                BattleWindow/               伤害计算
                    BattleWindow.qml
                FloorSheetWindow/           「这一层」小窗
                    FloorSheetWindow.qml

加东西的规则（用户："一层UI一个文件夹！！！子界面写在子文件夹下，按此嵌套"）：

1. **一层 UI 一个文件夹**：主窗口和它的窗口级子界面在 `qml/` 根；
   独立窗口各自一个文件夹；那扇窗自己的覆盖层放进**它自己的文件夹**里。
2. **能独立存在就单独一份文件**，到处复用的小件放 `components/`。
3. **搬出去的文件跟主窗口说话只能走 `host`**：`property var host` + `host.xxx`，
   由创建方递进来（`BattleWindow { host: win }`）。配色/字体不用 host，直接 `Theme.xxx`。
4. **每个文件夹自己 `import`**：`import "."` 本目录，`import "../../components"`
   这种相对路径指向共用件。

两个加载上的要点：

1. **必须按磁盘路径加载**（`load_into`），不能 `loadData(qrc:/…)` ——
   多文件要靠相对 `import` 找组件，qrc 路径下没有这些文件。
2. `source()` 返回**整棵树所有** `.qml` 拼起来的全文，`OVERLAY_QML` 还是它 ——
   `tests/test_editor.py`（每个 `controller.xxx(` 必须是 @Slot）和
   `tools/dump_ui_text.py`（文案扫描）都是按全文扫的，拆多少层都不能少看一块。
"""

import io
import os

from PySide6.QtCore import QUrl

# 界面全在 views/ 里；这个文件（和 controller/ toolkit/）是 Python，不混放。
QML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "views")
QML_FILE = os.path.join(QML_DIR, "MainWindow.qml")


def qml_files() -> list:
    """整棵树里的全部 `.qml`（`MainWindow.qml` 排第一，其余按相对路径排序）。"""
    found = []
    for root, dirs, names in os.walk(QML_DIR):
        dirs.sort()
        for name in sorted(names):
            if name.endswith(".qml"):
                found.append(os.path.join(root, name))
    head = QML_FILE
    found.sort(key=lambda path: (path != head, path))
    return found


def source() -> str:
    """全部 QML 源码（拼起来，供扫描/测试用；加载请用 `load_into`）。"""
    parts = []
    for path in qml_files():
        with io.open(path, encoding="utf-8") as handle:
            parts.append(handle.read())
    return "\n".join(parts)


def qml_url() -> QUrl:
    """主窗口那份文件的地址（多文件 QML 的入口）。"""
    return QUrl.fromLocalFile(QML_FILE)


def load_into(engine) -> bool:
    """把界面装进 QQmlApplicationEngine（按磁盘路径加载，相对 import 才找得到）。"""
    engine.load(qml_url())
    return bool(engine.rootObjects())


OVERLAY_QML = source()

__all__ = ["OVERLAY_QML", "QML_DIR", "QML_FILE", "load_into", "qml_files",
           "qml_url", "source"]
