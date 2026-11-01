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
// 配色（IntelliJ Light 一路）：冷灰白底 + 近黑字 + 唯一一个蓝色强调色。
// 层次靠 1px 分隔线和极淡的灰底，不靠边框和阴影堆。
// `amber` / `amberInk` 是旧名字（原来是琥珀金，现在是强调蓝）：各界面逐个换样式时
// 一并改成 `accent`，不为了改名去碰还没轮到的文件。
QtObject {
    readonly property string uiFont: "Microsoft YaHei UI"
    readonly property string monoFont: "Consolas"

    // 面板底 / 浮起的面（弹层、输入框内部）/ 凹下去的底（输入框、悬停、分区标题条）
    readonly property color paper: "#FFFFFF"
    readonly property color paperHi: "#FFFFFF"
    readonly property color paperLo: "#F7F8FA"
    // 三层面：窗口底（canvas）→ 卡片（paper，Card.qml）→ 卡里凹下去的小块（tile）
    readonly property color canvas: "#EEF0F3"
    readonly property color tile: "#F4F5F8"
    // 卡片外框、卡片底沿的一线暗边（模拟投影，比真阴影便宜）
    readonly property color cardEdge: "#E2E5EA"
    readonly property color cardShade: "#DADDE3"
    // 窗口投影
    readonly property color windowShadow: "#40101828"
    // 窗口最外圈留给投影的透明边（主窗口和所有子窗口一样宽）
    readonly property int windowInset: 10
    // 小胶囊（Chip）的底
    readonly property color chip: "#EEF0F4"
    // 悬停和按下的灰底（行、图标按钮）
    readonly property color hover: "#EBECF0"
    // 外框 / 分隔线
    readonly property color edge: "#DFE1E5"
    readonly property color hairline: "#EBECF0"
    // 输入框外框（比分隔线深一档，看得出是能点的）
    readonly property color fieldEdge: "#C9CCD6"
    readonly property color ink: "#1E1F22"
    readonly property color ink2: "#4E5157"
    readonly property color ink3: "#818594"
    readonly property color amber: "#3574F0"
    readonly property color amberInk: "#FFFFFF"
    readonly property color amberHover: "#2E67D6"
    readonly property color amberPress: "#2859B8"
    // 强调色的淡底（选中行、聚焦光圈）
    readonly property color amberSoft: "#E8F0FE"
    readonly property color danger: "#DB5860"
    readonly property color dangerSoft: "#FBEBEC"
    readonly property color dangerEdge: "#EFB8BC"
    // 效果标记的三个颜色（伤害计算里资源缩略图左下角那种小字）：
    // 攻击 = 红、防御 = 蓝、魔防 = 绿（用户 2026-10-28 点的颜色）
    readonly property color markAtk: "#C23B2E"
    readonly property color markDef: "#2F6FA8"
    readonly property color markMdef: "#3E8E5A"

    // 尺寸：圆角、控件高度（按钮/输入框/图标按钮同高，同一排才齐）
    readonly property int radius: 4
    readonly property int controlH: 24
}
