pragma Singleton
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 配色和字体（单例，靠 qmldir 注册成 Theme）。

import QtQuick

// 配色和字体：整份界面**只有这一处定义**（AGENTS.md §0："一切以代码最合理优先"）。
//
// 为什么单独一个单例：以前这 12 个值长在主窗口里（`win.amber` / `win.uiFont`…）。
// 子界面一搬出去（views/battle_calc/BattleWindow.qml），就只能靠 `property var host` 回头读
// 主窗口 —— 于是每个子文件都要多传一次 host，还多出"host 还没赋值"的中间状态。
// 配色和字体是静态的，子文件直接 `Theme.amber` 就行；`host` 只留给真正的业务状态。
//
// 用它的前提：同目录有 `qmldir`（`singleton Theme 1.0 Theme.qml`），
// 文件里写 `import "."`（直接子目录里 `import ".."`）。
QtObject {
    readonly property string uiFont: "Microsoft YaHei UI"
    readonly property string monoFont: "Consolas"

    readonly property color paper: "#F4F0E7"
    readonly property color paperHi: "#FFFCF6"
    readonly property color paperLo: "#F7F2E8"
    readonly property color edge: "#D5CCBA"
    readonly property color hairline: "#E2DACA"
    readonly property color ink: "#1D1A14"
    readonly property color ink2: "#5E5749"
    readonly property color ink3: "#8C8372"
    readonly property color amber: "#B4842A"
    readonly property color amberInk: "#FFF8EA"
    readonly property color danger: "#B4452A"
    // 效果标记的三个颜色（伤害计算里资源缩略图左下角那种小字）：
    // 攻击 = 红、防御 = 蓝、魔防 = 绿（用户 2026-10-28 点的颜色）
    readonly property color markAtk: "#C23B2E"
    readonly property color markDef: "#2F6FA8"
    readonly property color markMdef: "#3E8E5A"
}
