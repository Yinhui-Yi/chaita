"""一次性迁移：把 chaita/ui/main.py（8300+ 行）拆成目录结构。

拆成什么样：
    chaita/ui/__init__.py        Qt 的 DLL/QML 路径（必须先于任何 PySide6 导入）
    chaita/ui/constants.py           常量、资源路径、进程启动标记
    chaita/ui/qml/MainWindow.qml    界面（原来是 Python 里的字符串）
    chaita/ui/qml/__init__.py    把 MainWindow.qml 读成 OVERLAY_QML
    chaita/ui/toolkit/           与界面无关的纯函数，按"跟谁打交道"分文件
    chaita/ui/controller/        控制器，按功能区拆成 mixin，base.py 组装
    chaita/ui/startup.py         崩溃日志、渲染后端、main()、收尾
    chaita/ui/main.py         门面：把名字重新摆出来（老调用方一行都不用改）

跑法（**输入是拆分前那份 overlay.py**，默认取备份；现在仓库里的 overlay.py 已经是门面了，
拿它当输入自然找不到 `class Controller`）：

    python tools/_split_overlay.py            干跑，只打印分组和没解析出来的名字
    python tools/_split_overlay.py --write    真的写文件（子包会被覆盖）

想验证"这套拆分现在还 reproduce 得出来"，干跑一次就够了：它会打印每个文件的行数，
和 docs/REDESIGN_NOTES.md 第 9 节的表对得上就说明脚本没漂。
"""

import argparse
import ast
import builtins
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "chaita", "ui")
BACKUP = os.path.join(ROOT, "logs", "backup")
DEFAULT_SOURCE = os.path.join(BACKUP, "overlay_before_split_2026.py")

# ---- 控制器：方法名 -> 文件 ----
CONTROLLER_GROUPS = {
    "reading": """
        readOnly readGame retryTask cancelTask _start_task _capture _read_worker
        _read_worker_once _start_items_task _finish_items_task _attach_items
        _apply_floor _start_scan_task _apply_scan _deliver _deliver_monsters _finish
    """,
    "monsters": """
        _get_monsters _map_monster_names _get_skill_stats _get_monster_templates
        _get_skill_catalog _get_tower_label clearMonsters itemIconChoices setItemIcon
        libraryChoices monsterIconChoices libraryUrl itemChoices addMonster
        addMonsterTpl saveMonsterFull saveMonster moveMonster removeMonster
        setMonsterSkillValue monDragStart monDragFinish _tick_mon_drag
        _get_mon_drag_from _get_mon_drag_to
    """,
    "floors": """
        _get_map_history clearMaps _store_map_entry refreshFloorCounts saveFloorMemo
        _find_floor _get_counting_floor removeFloor markFloorSaved _get_saved_key
        _mark_saved _clear_saved addFloorMonster addFloorMonsterFull
        saveFloorMonsterFull saveFloorMonster removeFloorMonster
        saveFloorMonsterField toggleFloorMonsterDone addItem addItemFull saveItem
        saveItemFull saveItemField removeItem toggleFloorItemDone _toggle_done
    """,
    "status": """
        _get_status_text _get_attr_text _get_items_text _get_gold_text
        _get_status_data _get_status_at _apply_status _get_updating updateStatus
        _update_worker _update_done _apply_person
    """,
    "chat": """
        _get_chat_reply _get_error_text _get_chatting sendChat _chat_worker _chat_done
    """,
    "base": """
        __init__ _start_thread _run_ui_call _sample_foreground _get_reading
        _get_active_reads _get_tasks _set_task _post _job_done _task_src_path
        _load_task_src animateSize cancelSizeAnim _tick_size attach
        markGeometryReady rememberWindow _flush_ui_state _begin_shutdown quit log
        dragStart dragEnd _tick_drag restoreSession discardSession _get_session_hint
    """,
}

# ---- 模块级函数：函数名 -> 文件 ----
TOOLKIT_GROUPS = {
    "api": "_api_key",
    "desktop": "_cursor_pos _cursor_down NativeHitTest",
    "library": ("_import_icon _skill_items_from_text _parse_skill_payload "
                "_monster_skill_items _skill_names _load_templates_from_db "
                "_load_skill_catalog _load_monster_templates"),
    "pictures": "_save_temp _save_thumb",
    "texts": "_split_status _carry_row _floor_text",
    "diagnostics": "_write_error_log",
    "state": ("_save_session _load_session _session_hint _ui_state_enabled "
              "_load_ui_state _save_ui_state _geometry_from_state "
              "_apply_ui_state _place_right"),
}

STARTUP_FUNCS = "_enable_crash_log _render_backend_hint main _teardown"

FILE_DOCS = {
    "const": "界面用到的常量、资源路径、进程启动标记。改数值只改这里。",
    "startup": "启动与收尾：崩溃日志、渲染后端、main()、按顺序拆窗口。",
    "toolkit/api": "模型服务的入口：API key 只在 config 里定义，这里转发。",
    "toolkit/desktop": "和 Windows 桌面打交道：光标位置、按键状态、边缘命中测试。",
    "toolkit/library": "怪物模板库与技能：读 SQLite 模板、技能解析、用户上传的缩略图。",
    "toolkit/pictures": "截图落盘：临时大图与列表缩略图。",
    "toolkit/texts": "把结构化数据变成界面上给人看的文字。",
    "toolkit/diagnostics": "读取失败时落一份现场，方便事后查。",
    "toolkit/state": "会话记录与窗口状态的读写（logs/ 下那两个 json）。",
    "controller/base": "控制器地基：线程、任务队列、窗口尺寸与拖动、退出。",
    "controller/reading": "「读取」这条线：抓图 → 判类型 → 读内容 → 落地到界面。",
    "controller/monsters": "怪物区：模板库、手动加怪、拖动排序、技能数值。",
    "controller/floors": "地图区与「这一层」：每层记录、备忘、刷新、资源行编辑。",
    "controller/status": "状态区：属性/道具/金币文本、选手信息与更新线程。",
    "controller/chat": "对话区：发一句话、把模型的回答贴回来。",
}

PYSIDE = {
    "QAbstractNativeEventFilter": "PySide6.QtCore",
    "QObject": "PySide6.QtCore",
    "Property": "PySide6.QtCore",
    "Qt": "PySide6.QtCore",
    "QTimer": "PySide6.QtCore",
    "QUrl": "PySide6.QtCore",
    "Signal": "PySide6.QtCore",
    "Slot": "PySide6.QtCore",
    "QCoreApplication": "PySide6.QtCore",
    "QEvent": "PySide6.QtCore",
    "QGuiApplication": "PySide6.QtGui",
    "QImage": "PySide6.QtGui",
    "QQmlApplicationEngine": "PySide6.QtQml",
}

STDLIB = {
    "ctypes": "import ctypes",
    "json": "import json",
    "os": "import os",
    "re": "import re",
    "sys": "import sys",
    "threading": "import threading",
    "time": "import time",
}

BUILTIN = set(dir(builtins)) | {"self", "cls", "__file__", "__name__"}


def code_only(text: str) -> str:
    """去掉注释和字符串，只留代码里的名字。

    不这么做的话，"Windows"/"QML"/"SELECT" 这些出现在注释里的词会被当成引用，
    报出一堆假警报，真正漏掉的 import 反而看不见。
    """
    import io
    import tokenize

    pieces = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            if token.type == tokenize.NL:
                pieces.append(" ")
                continue
            pieces.append(token.string)
    except (tokenize.TokenError, IndentationError):
        return text
    return " ".join(pieces)


def words(text: str) -> set:
    """代码里引用到的名字：只看 NAME 词，跳过 `obj.attr` 里的 attr 和关键字参数。"""
    import io
    import tokenize

    found = set()
    previous = None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        return set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)", text))
    for token in tokens:
        if token.type == tokenize.NAME:
            if previous is None or previous.string != ".":
                found.add(token.string)
        if token.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                              tokenize.DEDENT, tokenize.COMMENT):
            previous = token
    return found


def strip_docstring(node):
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def block_start(node, lines):
    """这个节点（连注释）从第几行开始（1 基）。"""
    first = node.lineno
    if getattr(node, "decorator_list", None):
        first = min([d.lineno for d in node.decorator_list] + [first])
    while first > 1 and lines[first - 2].lstrip().startswith("#"):
        first -= 1
    return first


def read_source(path: str) -> list:
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    if not any(line.startswith("OVERLAY_QML") for line in lines):
        raise SystemExit(
            "这个文件里没有 OVERLAY_QML，不像是拆分前那份 overlay.py：%s\n"
            "（现在仓库里的 chaita/ui/main.py 已经是门面了，请指向备份，"
            "默认就是 logs/backup/overlay_before_split_2026.py）" % path)
    return lines


def top_level(tree, lines):
    """模块级：函数/类/赋值 -> [(kind, name, first, last, text)]，按行号排。"""
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(("func", node.name, block_start(node, lines),
                        node.end_lineno))
        elif isinstance(node, ast.ClassDef):
            out.append(("class", node.name, block_start(node, lines),
                        node.end_lineno))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.ImportFrom,
                              ast.Import)):
            targets = []
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        targets.append(target.id)
                    elif isinstance(target, ast.Tuple):
                        # `_HTLEFT, _HTRIGHT = 10, 11`：一拖多的每个名字都要认领
                        targets.extend(e.id for e in target.elts
                                       if isinstance(e, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            if isinstance(node, (ast.ImportFrom, ast.Import)):
                targets = ["<import>"]
            for name in targets:
                out.append(("assign", name, block_start(node, lines),
                            node.end_lineno))
    out.sort(key=lambda item: item[2])
    return out


def take(lines, first, last):
    return "\n".join(lines[first - 1:last])


def controller_chunks(tree, lines):
    """Controller 的每个方法 -> [(name, first, last)]。"""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Controller":
            out = []
            for item in strip_docstring(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((item.name, block_start(item, lines),
                                item.end_lineno))
            return out
    raise SystemExit("没找到 class Controller")


def class_body_assigns(tree, lines):
    """Controller 类体里不是方法的那些语句（信号、类属性）。"""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Controller":
            out = []
            for item in strip_docstring(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                out.append((block_start(item, lines), item.end_lineno))
            return out
    return []


def qml_text(tree):
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "OVERLAY_QML":
                    return node.value.value
    raise SystemExit("没找到 OVERLAY_QML")


def import_block(text, sources, own=(), depth=2):
    """按实际用到的名字生成 import 段（不写没用到的，也不 import 自己文件里的）。"""
    used = words(text) - set(own)
    lines = []

    stdlib = sorted(STDLIB[name] for name in used & set(STDLIB))
    if stdlib:
        lines.extend(stdlib)
        lines.append("")

    pyside = {}
    for name in used & set(PYSIDE):
        pyside.setdefault(PYSIDE[name], []).append(name)
    for module in sorted(pyside):
        names = ", ".join(sorted(pyside[module]))
        lines.append("from %s import %s" % (module, names))
    if pyside:
        lines.append("")

    groups = {}
    for name in used:
        module = sources.get(name)
        if module:
            groups.setdefault(module, []).append(name)
    for module in sorted(groups):
        prefix = "." * depth
        lines.append("from %s%s import %s"
                     % (prefix, module, ", ".join(sorted(groups[module]))))
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def unknown(text, sources, extra=()):
    """引用了、但既不是内置、又没来源的名字（大概就是局部变量，但要人眼看一眼）。"""
    import keyword

    used = words(text)
    known = (set(sources) | set(PYSIDE) | set(STDLIB) | BUILTIN
             | set(keyword.kwlist) | set(STARTUP_FUNCS.split()) | set(extra))
    local = set(re.findall(r"(?:^|[\s(,=])([a-z_]\w*)\s*(?:=[^=]|\+=)",
                           code_only(text)))
    return sorted(used - known - local)


def qualify_class_body(text, mapping, mixin):
    """类体里的 Property 引用的是方法名；方法搬进 mixin 之后要写成 Mixin.方法。"""
    def replace(match):
        name = match.group(1)
        module = mapping.get(name)
        if module is None:
            return name
        return "%s.%s" % (mixin[module], name)

    return re.sub(r"\b(_\w+)\b", replace, text)


def deepen_imports(text):
    """从一个子包里看父包要多一点：`from .. import trace` -> `from ... import trace`。

    只作用于搬进子包（toolkit/、controller/）的函数体；文件头里那些 import 是
    生成时按正确层级写好的，不能再动。
    """
    def replace(match):
        return "%sfrom .%s" % (match.group(1), match.group(2))

    return re.sub(r"(?m)^(\s*)from (\.+)", replace, text)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--from", dest="source", default=DEFAULT_SOURCE,
                        help="拆分前那份 overlay.py（默认拿备份）")
    args = parser.parse_args()

    lines = read_source(args.source)
    tree = ast.parse("\n".join(lines))

    blocks = top_level(tree, lines)
    methods = controller_chunks(tree, lines)
    body_assigns = class_body_assigns(tree, lines)

    # ---- 名字 -> 来源模块 ----
    sources = {}
    for kind, name, first, last in blocks:
        if kind == "func":
            for module, names in TOOLKIT_GROUPS.items():
                if name in names.split():
                    sources[name] = "toolkit." + module
            if name in STARTUP_FUNCS.split():
                sources[name] = "startup"
        elif kind == "class":
            if name == "NativeHitTest":
                sources[name] = "toolkit.desktop"
        elif kind == "assign" and name != "<import>" and name not in (
                "OVERLAY_QML", "_LIBRARY"):
            sources[name] = "const"
    sources["Controller"] = "controller"

    # ---- 模块级函数的正文 ----
    funcs = {name: take(lines, first, last)
             for kind, name, first, last in blocks if kind == "func"}
    classes = {name: take(lines, first, last)
               for kind, name, first, last in blocks if kind == "class"}
    assigns = [(name, take(lines, first, last))
               for kind, name, first, last in blocks
               if kind == "assign" and name != "<import>"]
    imports_from = [take(lines, first, last)
                    for kind, name, first, last in blocks
                    if kind == "assign" and name == "<import>"
                    and "paths" in take(lines, first, last)]

    qml = qml_text(tree)

    # mixin 类名（先算出来，类体里的 Property 要用）
    mixin = {"reading": "ReadingMixin", "monsters": "MonstersMixin",
             "floors": "FloorsMixin", "status": "StatusMixin",
             "chat": "ChatMixin", "base": "BaseMixin"}

    # ---- 检查：每个方法都有归属 ----
    mapping = {}
    for module, names in CONTROLLER_GROUPS.items():
        for name in names.split():
            mapping[name] = module
    missing = [name for name, _, _ in methods if name not in mapping]
    if missing:
        print("!! 没有分组的控制器方法:", missing)
    stray = [name for name in mapping if name not in {n for n, _, _ in methods}]
    if stray:
        print("!! 分组里有不存在的方法:", stray)

    grouped = set(STARTUP_FUNCS.split())
    for names in TOOLKIT_GROUPS.values():
        grouped |= set(names.split())
    homeless = [name for kind, name, _, _ in blocks
                if kind == "func" and name not in grouped]
    if homeless:
        print("!! 模块级函数没分到文件（会丢！）:", homeless)

    # ---- toolkit 文件 ----
    outputs = {}
    for module, names in TOOLKIT_GROUPS.items():
        parts, used_names = [], []
        for name in names.split():
            if name in funcs:
                parts.append(funcs[name])
                used_names.append(name)
            elif name in classes:
                parts.append(classes[name])
                used_names.append(name)
        body = deepen_imports("\n\n".join(parts))
        doc = FILE_DOCS["toolkit/" + module]
        header = '"""%s"""\n' % doc
        imports = import_block(body, sources, own=set(used_names), depth=2)
        outputs[os.path.join("toolkit", module + ".py")] = (
            header + "\n" + imports + "\n\n\n" + body + "\n")
        print("toolkit/%-12s %3d 行  %s" % (module + ".py", len(body.splitlines()),
                                            " ".join(used_names)))
        bad = unknown(body, sources)
        if bad:
            print("    可能没解析:", bad)

    # ---- constants.py ----
    # OVERLAY_QML 是界面正文（搬去 qml/MainWindow.qml），_LIBRARY 是 Qt 路径（搬去
    # 包初始化），这两个不留在 constants.py 里。
    skip = {"OVERLAY_QML", "_LIBRARY"}
    const_body = "\n\n".join(text for name, text in assigns
                             if name not in skip
                             and not text.lstrip().startswith("os.environ"))
    const_imports = import_block(const_body, sources,
                                own={name for name, _ in assigns},
                                depth=1)
    const_head = ('"""%s"""\n' % FILE_DOCS["const"]) + "\n"
    const_head += const_imports + "\n"
    if imports_from:
        const_head += "\n".join(imports_from) + "\n"
    outputs["constants.py"] = const_head + "\n\n" + const_body + "\n"
    print("constants.py        %3d 行" % len(const_body.splitlines()))
    bad = unknown(const_body, sources)
    if bad:
        print("    可能没解析:", bad)

    # ---- 控制器 ----
    header_imports = {}
    for module, names in CONTROLLER_GROUPS.items():
        parts = []
        for name in names.split():
            for method, first, last in methods:
                if method == name:
                    parts.append(take(lines, first, last))
        body = deepen_imports("\n\n".join(parts))
        header_imports[module] = body
        if module != "base":
            outputs[os.path.join("controller", module + ".py")] = None  # 稍后填
        print("controller/%-10s %3d 行" % (module + ".py", len(body.splitlines())))
        bad = unknown(body, sources)
        if bad:
            print("    可能没解析:", bad)


    for module in CONTROLLER_GROUPS:
        if module == "base":
            continue
        body = header_imports[module]
        imports = import_block(body, sources, depth=2,
                               own=set(CONTROLLER_GROUPS[module].split()))
        text = ('"""%s"""\n' % FILE_DOCS["controller/" + module]) + "\n" \
            + imports + "\n\n\nclass %s:\n" % mixin[module] + body + "\n"
        outputs[os.path.join("controller", module + ".py")] = text

    # base.py 有两个类：BaseMixin（可搬走的方法）+ Controller（类体里的信号、
    # __init__、以及 mixin 的组装顺序）。__init__ 必须留在 Controller 里，
    # 它写的那些状态是别的 mixin 共用的。
    assigns_text = qualify_class_body(
        "\n\n".join(take(lines, first, last) for first, last in body_assigns),
        mapping, mixin)
    bases = ", ".join(mixin[m] for m in ("chat", "floors", "monsters",
                                         "reading", "status", "base"))
    mixin_imports = "\n".join(
        "from .%s import %s" % (m, mixin[m])
        for m in ("chat", "floors", "monsters", "reading", "status"))
    init_text = ""
    for method, first, last in methods:
        if method == "__init__":
            init_text = deepen_imports(take(lines, first, last))
    parts = []
    for name in CONTROLLER_GROUPS["base"].split():
        if name == "__init__":
            continue
        for method, first, last in methods:
            if method == name:
                parts.append(take(lines, first, last))
    base_methods = deepen_imports("\n\n".join(parts))
    base_imports = import_block(base_methods + "\n" + init_text + "\n"
                                + assigns_text + "\nQObject", sources,
                                depth=2,
                                own=set(CONTROLLER_GROUPS["base"].split()))
    base_text = ('"""%s"""\n' % FILE_DOCS["controller/base"]) + "\n" \
        + base_imports + "\n" + mixin_imports + "\n\n\n" \
        + "class BaseMixin:\n" + base_methods + "\n\n\n" \
        + "class Controller(%s, QObject):\n" % bases \
        + (assigns_text + "\n\n" if assigns_text else "") \
        + init_text + "\n"
    outputs[os.path.join("controller", "base.py")] = base_text
    outputs[os.path.join("controller", "__init__.py")] = (
        '"""控制器：按功能区拆成 mixin，base.py 把它们拼成一个 QObject。"""\n\n'
        "from .base import Controller\n\n"
        '__all__ = ["Controller"]\n')

    # ---- qml ----
    outputs[os.path.join("qml", "__init__.py")] = (
        '"""界面文件：QML 单独一份，不再塞进 Python 字符串里。"""\n\n'
        "import os\n\n"
        'QML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
        '                        "MainWindow.qml")\n\n\n'
        "def source() -> str:\n"
        '    """整份 QML 源码。加载走 loadData，和以前一样按 qrc 路径当基准。"""\n'
        '    with open(QML_FILE, encoding="utf-8") as handle:\n'
        "        return handle.read()\n\n\n"
        "OVERLAY_QML = source()\n\n"
        '__all__ = ["OVERLAY_QML", "QML_FILE", "source"]\n')
    outputs[os.path.join("qml", "MainWindow.qml")] = qml

    # ---- startup.py ----
    startup_names = STARTUP_FUNCS.split()
    body = "\n\n".join(funcs[name] for name in startup_names if name in funcs)
    imports = import_block(body, sources, own=set(startup_names), depth=1)
    # main() 要拿界面正文去 loadData；它住在 qml/ 里，不在这张名字表上
    imports += "\nfrom .qml import OVERLAY_QML"
    outputs["startup.py"] = ('"""%s"""\n' % FILE_DOCS["startup"]) + "\n" \
        + imports + "\n\n\n" + body + "\n"
    print("startup.py      %3d 行" % len(body.splitlines()))
    bad = unknown(body, sources)
    if bad:
        print("    可能没解析:", bad)

    # ---- overlay.py 门面 ----
    # 老调用方按 overlay.<名字> 取，所以常量、工具函数、启动函数全都再摆一遍。
    facade_toolkit = {}
    facade_startup = []
    for name in sorted(sources):
        module = sources[name]
        if module == "controller" or module == "const":
            continue
        if module == "startup":
            facade_startup.append(name)
            continue
        facade_toolkit.setdefault(module, []).append(name)

    def one_per_line(names):
        return "".join("    %s,\n" % name for name in sorted(names))

    facade = (
        '"""ChaitaAssistant 悬浮层（门面）。\n\n'
        "界面本身的实现在同目录下这几处，这个文件只把名字摆出来：\n"
        "    qml/MainWindow.qml     界面（QML 单独一份，不再塞进 Python 字符串）\n"
        "    constants.py            常量与资源路径\n"
        "    toolkit/            与界面无关的纯函数（桌面 / 素材库 / 截图 / 文本 / 状态 / 日志）\n"
        "    controller/         控制器（按功能区拆成 mixin，base.py 组装）\n"
        "    startup.py          启动、收尾、崩溃日志\n\n"
        "tests 和 tools 一直按 `overlay.<名字>` 取，所以这里全部保留。`os` 与\n"
        "`QGuiApplication` 也摆在门面上：测试按 `overlay.os` / `overlay.QGuiApplication`\n"
        "打桩，打桩会按名字铺到真正持有它的子模块（tests/ui_patch.py）。\n"
        '"""\n\n'
        "import os  # noqa: F401\n\n"
        "from PySide6.QtGui import QGuiApplication  # noqa: F401\n\n"
        "from .constants import (  # noqa: F401\n"
        + one_per_line(c for c, module in sources.items() if module == "const")
        + ")\n"
        "from .controller import Controller  # noqa: F401\n"
        "from .qml import OVERLAY_QML  # noqa: F401\n"
        "from .startup import (  # noqa: F401\n"
        + one_per_line(facade_startup)
        + ")\n")
    for module in sorted(facade_toolkit):
        names = ", ".join(sorted(facade_toolkit[module]))
        facade += "from .%s import %s  # noqa: F401\n" % (module, names)
    facade += "\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n"
    outputs["overlay.py"] = facade

    ui_init = (
        '"""界面层。\n\n'
        "Qt 的 DLL 与 QML 模块都在 conda 环境的 Library 下，而 PySide6 包里没有\n"
        "qt.conf，所以路径必须在**任何模块 import PySide6 之前**指好，否则\n"
        "QML 加载会报「找不到 qtquick2plugin.dll」。放在包初始化里，谁先导入\n"
        '这个包都先经过这里。\n"""\n\n'
        "import os\nimport sys\n\n"
        '_LIBRARY = os.path.join(sys.prefix, "Library")\n\n'
        'os.environ["PATH"] = os.pathsep.join(\n'
        '    [os.path.join(_LIBRARY, "bin"), os.environ.get("PATH", "")])\n'
        'os.environ.setdefault("QML2_IMPORT_PATH",\n'
        '                      os.path.join(_LIBRARY, "lib", "qt6", "qml"))\n'
        'os.environ.setdefault("QT_PLUGIN_PATH",\n'
        '                      os.path.join(_LIBRARY, "plugins"))\n')
    outputs[os.path.join("__init__.py")] = ui_init

    total = sum(len(text.splitlines()) for key, text in outputs.items()
                if key.endswith((".py", ".qml")))
    print("合计 %d 行，%d 个文件" % (total, len(outputs)))

    if not args.write:
        print("（干跑，没写文件；加 --write 才落盘）")
        return 0

    for rel, text in outputs.items():
        write(os.path.join(UI, rel), text)
    print("已写入 chaita/ui/（拆分前的原文在 %s）" % args.source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
