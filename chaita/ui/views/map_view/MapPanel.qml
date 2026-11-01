import QtQuick
// 主界面「地图」那一栏的正身：左边侧栏快速切层，右边**这一层的大图**，
// 其余层的图压在大图后面、只露一角（用户 2026-10-30："把主界面的地图做大！、
// 多张地图不要重叠显示下层的只留一角！做侧边栏快速切换"）。
//
// 图层都摊在"图实际画出来的那一块"上（从下往上）：
//   截图 → 楼梯 → 路线 → 格子编辑 → 路线对比高亮
// 状态全在主窗口（`host.mapFloor` / `gridEditOn` / `mapHi*` …），这里只画和点。
import "route_layer"
import "grid_layer"
import "stair_layer"
import "../shared"

Item {
    id: panel

    property var host

    // 侧栏宽（只写层号，写全名太占地方）
    readonly property int railW: 46
    // 每多一层往后错 14px，露出"一角"；只露**一张**（用户："不要叠太多"），
    // 再多层靠左边的侧栏切
    readonly property int peekStep: 14
    readonly property int peekMax: 1
    readonly property int gap: 6
    // 大图边长：撑满剩下的宽度，再给后面的卡片留出错开的 24px
    readonly property real cardSide: Math.max(80, Math.min(
        width - railW - gap - peekStep * peekMax, 360))
    readonly property real stackH: cardSide + peekStep * peekRows.length

    objectName: "mapPanel"
    width: parent ? parent.width : 0
    // 点空白时加一：所有开着的输入框收到就各自收起来并生效
    property int closeTick: 0
    // 现在开着的那一格（点别处就收起来；点在它自己身上不算）
    property var openField: null
    // 这一栏多高：大图（含错开的角）+ 底下那条 22
    height: host.mapCollapsed || host.floorList.length === 0
            ? 0 : stackH + 32

    // 现在这一层的记录
    readonly property var entry: host.mapEntry(host.mapFloor)

    // 侧栏那些行：楼层号 + 剩几只（从上往下 = 高楼在上）
    // 侧栏一层一行，**只写层号**（用户 2026-10-31："加你妈逼的剩怪数…删了"）
    readonly property var railRows: {
        var list = host.mapFloors()
        var out = []
        for (var i = list.length - 1; i >= 0; i--) {
            var one = list[i] || {}
            var name = String(one.floor || "")
            out.push({ "floor": name,
                       "label": panel.shortName(name) })
        }
        return out
    }

    // 压在大图后面的那几层（每层只露右下角一条）
    readonly property var peekRows: {
        var list = host.mapFloors()
        var names = []
        for (var i = 0; i < list.length; i++)
            names.push(String((list[i] || {}).floor || ""))
        var index = names.indexOf(host.mapFloor)
        var out = []
        if (index < 0)
            return out
        // 屏幕上的顺序：往下就是往下层（楼层号 -1）
        for (var step = 1; step <= panel.peekMax; step++) {
            var next = index - step
            if (next < 0)
                break
            var row = list[next] || {}
            out.push({ "floor": String(row.floor || ""),
                       "url": String(row.url || ""),
                       "label": panel.shortName(String(row.floor || "")),
                       "x": step * panel.peekStep,
                       "y": step * panel.peekStep })
        }
        return out
    }

    // 层名只留末尾的数字（"通天塔3" → "3"）；没数字就写前两个字
    function shortName(floorText) {
        var text = String(floorText || "")
        var digits = /(\d+)\s*$/.exec(text)
        if (digits)
            return digits[1]
        return text.length > 2 ? text.substring(0, 2) : text
    }

    // 侧栏一行有多高：一行一层，最多 12 行，多了自己滚
    readonly property real railRowH: Math.max(
        18, Math.min(26, (stackH - 4) / Math.max(1, railRows.length)))

    visible: !host.mapCollapsed && host.floorList.length > 0

    // ---------- 左边：侧栏快速切层 ----------
    ListView {
        id: rail
        objectName: "floorRailList"
        x: 0
        y: 0
        width: panel.railW
        height: Math.min(panel.railRows.length * panel.railRowH + 2,
                         panel.stackH)
        clip: true
        spacing: 0
        model: panel.railRows
        boundsBehavior: Flickable.StopAtBounds

        delegate: Item {
            objectName: "floorRailRow"
            width: rail.width
            height: panel.railRowH
            readonly property bool active:
                String((modelData || {}).floor || "") === panel.host.mapFloor

            Rectangle {
                anchors.fill: parent
                anchors.rightMargin: 4
                anchors.topMargin: 1
                anchors.bottomMargin: 1
                radius: Theme.radius
                color: Theme.amberSoft
                visible: parent.active
            }
            Text {
                objectName: "floorRailName"
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                text: String((modelData || {}).label || "")
                color: parent.active ? Theme.amber : Theme.ink2
                font.family: Theme.monoFont
                font.pixelSize: 12
                font.bold: parent.active
                elide: Text.ElideRight
            }
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: panel.host.selectFloor(
                    String((modelData || {}).floor || ""))
                onWheel: function (wheel) {
                    panel.host.stepFloor(wheel.angleDelta.y > 0 ? 1 : -1)
                }
            }
        }
    }

    // ---------- 右边：这一层的大图 + 后面压着的几层 ----------
    Item {
        id: stack
        objectName: "mapStack"
        x: panel.railW + panel.gap
        y: 0
        width: panel.cardSide + panel.peekStep * panel.peekMax
        height: panel.cardSide + panel.peekStep * panel.peekMax
        clip: false

        // 后面的层：先画，只露右下角一条（点那一角 = 切到那层）
        Repeater {
            model: panel.peekRows
            delegate: Item {
                objectName: "mapPeek"
                x: Number(modelData.x)
                y: Number(modelData.y)
                width: panel.cardSide
                height: panel.cardSide

                Rectangle {
                    anchors.fill: parent
                    radius: 7
                    color: Theme.paperLo
                    border.width: 1
                    border.color: Theme.edge
                    clip: true
                    Image {
                        anchors.fill: parent
                        anchors.margins: 2
                        source: String(modelData.url || "")
                        visible: panel.host.hasUrl(String(modelData.url || ""))
                        fillMode: Image.PreserveAspectFit
                        smooth: false
                        asynchronous: true
                        opacity: 0.6
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: panel.host.selectFloor(
                        String(modelData.floor || ""))
                }
            }
        }

        // 顶层：选中那一层
        Rectangle {
            id: topCard
            objectName: "mapCard"
            x: 0
            y: 0
            width: panel.cardSide
            height: panel.cardSide
            radius: 7
            color: Theme.paperLo
            border.width: 1
            border.color: Theme.edge
            clip: true

            readonly property bool hasShot: panel.host.hasUrl(
                panel.host.sheetShot(panel.host.mapFloor))

            Image {
                id: shot
                objectName: "mapShot"
                anchors.fill: parent
                anchors.margins: 2
                source: panel.host.sheetShot(panel.host.mapFloor)
                visible: topCard.hasShot
                fillMode: Image.PreserveAspectFit
                smooth: false
                asynchronous: true
            }

            // 图层铺在"图实际画出来的那一块"上（贴外框格子会偏）
            Item {
                id: drew
                objectName: "mapLayers"
                anchors.fill: parent
                anchors.margins: 2

                readonly property real cellSide:
                    Math.max(4, panel.host.routeCell(panel.host.mapFloor,
                                                     width))

                StairLayer {
                    objectName: "stairLayer"
                    anchors.fill: parent
                    stairs: {
                        if (!controller)
                            return ({})
                        controller.mapHistory   // 绑一下：标完立刻重画
                        return panel.host.stairsOf(panel.host.mapFloor)
                    }
                    cell: parent.cellSide
                    upSrc: panel.host.itemIcon("stair_up")
                    downSrc: panel.host.itemIcon("stair_down")
                }

                RouteLayer {
                    id: routeLayer
                    objectName: "routeLayer"
                    anchors.fill: parent
                    floorName: panel.host.mapFloor
                    cellFloor: panel.host.mapFloor
                    cell: parent.cellSide
                    onStepped: function (cell) {
                        panel.host.routeEnterCell(routeLayer, cell)
                    }
                    // 编辑模式：**按下这一下就抓起这一格**（拖到「这一层」的怪/资源行上
                    // 松手就记下坐标）。不走长按 —— 用户 2026-10-31："从来都是点击选中，
                    // 什么时候要长按了"。格子永远走格子层的 `cellAt`（13×13 边界那条
                    // 规则只在那里写一份），两个层叠在同一块上、同一个坐标系。
                    grabOnPress: panel.editing
                    onGrabbed: function (x, y) {
                        var cell = gridLayer.cellAt(x, y)
                        if (cell.row === undefined)
                            return          // 13×13 之外不是格子，抓不起来
                        panel.beginCellDrag(cell.row, cell.col)
                    }
                    // 长按：起一条路线（编辑模式下走不到这里，见 `grabOnPress`）
                    onLongPressed: function (x, y) {
                        routeLayer.startAt(x, y)
                    }
                    // 点一下（不拖）：编辑模式里 = 选中这一格；平时 = 点楼梯换层
                    onTapped: function (cell, modifiers) {
                        if (!panel.editing) {
                            panel.host.tapMapCell(cell)
                            return
                        }
                        if (modifiers & Qt.ControlModifier)
                            panel.host.gridMultiToggle(cell.row, cell.col)
                        else
                            panel.host.gridPickCell(cell.row, cell.col)
                        panel.menuRow = -1
                    }
                    // 右键：编辑模式里出小窗（编号 + 复制坐标 / 清掉）
                    onRightTapped: function (cell, x, y) {
                        if (!panel.editing)
                            return
                        // **不动选择**：用户可能正勾着几格，右键看一眼坐标不该清掉
                        panel.host.gridPickMenuCell(cell.row, cell.col)
                        panel.menuRow = cell.row
                        panel.menuCol = cell.col
                        panel.showCellMenu(routeLayer.mapToItem(panel, x, y))
                    }
                    onFinished: function (cells) {
                        panel.host.storeRouteCells(cells)
                        routeLayer.clear()
                    }
                }

                GridLayer {
                    id: gridLayer
                    objectName: "gridLayer"
                    anchors.fill: parent
                    host: panel.host
                    floorName: panel.host.mapFloor
                    cell: parent.cellSide
                    side: panel.host.routeCols
                    editing: panel.editing
                    gridCells: {
                        if (!controller)
                            return []
                        controller.mapHistory
                        return controller.gridCells(panel.host.mapFloor)
                    }
                }

                // 编辑模式下左键单击选中的那一格：琥珀方框（右键菜单就作用在它上面）
                Rectangle {
                    objectName: "gridPickedCell"
                    readonly property var picked: panel.host.gridPicked || ({})
                    readonly property real side:
                        Math.max(6, panel.host.routeCell(panel.host.mapFloor,
                                                         parent.width))
                    visible: picked.row !== undefined
                             && panel.editing
                    x: Number(picked.col === undefined ? -1 : picked.col) * side
                    y: Number(picked.row === undefined ? -1 : picked.row) * side
                    width: side
                    height: side
                    radius: 2
                    color: Qt.rgba(0.84, 0.62, 0.18, 0.14)
                    border.width: 2
                    border.color: Theme.amber
                }

                // 路线对比点了某一行 → 这一格圈出来
                Rectangle {
                    objectName: "floorCellHighlight"
                    readonly property real side:
                        Math.max(6, panel.host.routeCell(
                            panel.host.mapFloor, parent.width))
                    visible: panel.host.mapHiFloor === panel.host.mapFloor
                             && Number(panel.host.mapHiRow) >= 0
                             && Number(panel.host.mapHiCol) >= 0
                    x: Math.max(0, Math.min(parent.width - side,
                            Number(panel.host.mapHiCol) * side))
                    y: Math.max(0, Math.min(parent.height - side,
                            Number(panel.host.mapHiRow) * side))
                    width: side
                    height: side
                    radius: 3
                    color: Qt.rgba(0.95, 0.76, 0.25, 0.28)
                    border.width: 2
                    border.color: "#8F5E0C"
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -3
                        radius: 6
                        color: "transparent"
                        border.width: 2
                        border.color: Qt.rgba(1, 1, 1, 0.88)
                    }
                }
            }

            // 这一层还没有截图
            Text {
                anchors.centerIn: parent
                visible: !topCard.hasShot
                text: "这一层还没有截图"
                color: Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 10
            }

            // 切层那一下：淡入 + 轻微上移（用户："切换层要有动画"）
            opacity: 1
            Behavior on opacity { NumberAnimation { duration: 140 } }
        }
    }

    // 右键小窗：哪一格、弹在哪（-1 = 没开）
    property int menuRow: -1
    property int menuCol: -1
    property real menuX: 0
    property real menuY: 0
    readonly property int menuW: 88
    readonly property int menuH: 58

    // 小窗摆在哪儿：**它挂在面板根上，不在被裁掉的大图里**
    // （用户 2026-10-31："我底部右键看不到复制选项" —— 原来它在大图里面，
    // 大图 clip 一裁，底边那几行的菜单就只剩上头那行编号）
    function showCellMenu(at) {
        var x = Math.max(2, Math.min(at.x, panel.width - panel.menuW - 4))
        var y = at.y + 8
        if (y + panel.menuH > panel.height - 2)
            y = Math.max(2, at.y - panel.menuH - 8)   // 下面放不下就翻到上面
        panel.menuX = x
        panel.menuY = y
    }

    // ---- 右键小窗：**格子编号单独一行**，下面是两个动作，没有别的话 ----
    Rectangle {
        objectName: "gridCellMenu"
        visible: panel.menuRow >= 0
        x: panel.menuX
        y: panel.menuY
        width: panel.menuW
        height: panel.menuH
        radius: 6
        color: Theme.paperHi
        border.width: 1
        border.color: Theme.edge
        z: 200

        Text {
            objectName: "gridMenuCoord"
            x: 8
            y: 4
            width: parent.width - 16
            height: 18
            verticalAlignment: Text.AlignVCenter
            text: panel.host.cellText(panel.host.mapFloor,
                                      panel.menuRow, panel.menuCol)
            color: Theme.ink
            font.family: Theme.monoFont
            font.pixelSize: 11
            font.bold: true
        }
        Rectangle {
            x: 6
            y: 23
            width: parent.width - 12
            height: 1
            color: Theme.hairline
        }
        Text {
            objectName: "gridMenuCopy"
            x: 8
            y: 26
            width: parent.width - 16
            height: 16
            verticalAlignment: Text.AlignVCenter
            text: "复制坐标"
            color: copyMouse.containsMouse ? Theme.amber : Theme.ink2
            font.family: Theme.uiFont
            font.pixelSize: 9
            MouseArea {
                id: copyMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    panel.host.gridCopyPicked()
                    panel.menuRow = -1
                }
            }
        }
        Text {
            objectName: "gridMenuClear"
            x: 8
            y: 41
            width: parent.width - 16
            height: 14
            verticalAlignment: Text.AlignVCenter
            text: "清掉"
            color: clearCellMouse.containsMouse ? Theme.danger : Theme.ink3
            font.family: Theme.uiFont
            font.pixelSize: 9
            MouseArea {
                id: clearCellMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    panel.host.gridClearPicked()
                    panel.menuRow = -1
                }
            }
        }
    }

    // 这一层标过楼梯没有（没标的话踩上去不会换层，底部要提醒一句）
    readonly property bool hasStairs: {
        if (!controller)
            return false
        controller.mapHistory          // 绑一下：标完立刻更新
        return panel.host.stairsOf(panel.host.mapFloor).length > 0
    }

    // 编辑模式只对"这一层"开
    readonly property bool editing:
        host.gridEditOn && host.gridEditFloor === host.mapFloor

    // 切层动画：`host.mapFloor` 一变，大图淡入一次
    Connections {
        target: panel.host
        function onMapFloorChanged() {
            if (!panel.visible)
                return
            topCard.opacity = 0.35
            fadeIn.restart()
        }
    }

    Timer {
        id: fadeIn
        interval: 16
        onTriggered: topCard.opacity = 1
    }

    // ---------- 底下那一条：这一层的一句话 + 操作 ----------
    Item {
        x: panel.railW + panel.gap
        y: panel.stackH + 8
        width: panel.width - panel.railW - panel.gap
        height: 22

        Text {
            objectName: "mapFoot"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, parent.width - tools.width - 8)
            // 三层意思，按优先级：换不了层的原因 → **这层还没标楼梯**（踩上去不换层，
            // 用户会以为坏了）→ 平时的"层名 · 还剩什么"
            text: host.mapHint !== ""
                  ? host.mapHint
                  : (!panel.hasStairs && !panel.editing
                     ? "楼梯没标"
                     : ((panel.entry.floor || "") + " · "
                        + host.mapMeta(host.mapFloor)))
            color: host.mapHint !== "" ? Theme.danger
                 : (!panel.hasStairs && !panel.editing ? Theme.amber
                                                       : Theme.ink3)
            font.family: Theme.uiFont
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        // 这一排动作**统一长相**（共用件 shared/TextBtn）：字号、颜色、间距、
        // 热区都一样，谁也不许自己再手写一套（用户：“设计要统一！！！！！！！！！！”）。
        // 全都在外面露着，不藏进编辑模式。
        Row {
            id: tools
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4

            TextBtn {
                objectName: "mapSheet"
                pill: true
                text: "清单 ›"
                onClicked: panel.host.openMapSheet()
            }
            TextBtn {
                objectName: "mapGridEdit"
                pill: true
                text: panel.editing ? "完成" : "编辑"
                accent: Theme.amber
                active: panel.editing
                onClicked: panel.host.gridEditToggle(panel.host.mapFloor)
            }
            TextBtn {
                objectName: "mapRefresh"
                pill: true
                text: "刷新"
                accent: Theme.amber
                onClicked: controller.refreshFloorCounts(panel.host.mapFloor)
            }
        }
    }

    // 编辑模式**按下**就抓起一格 → 拖到「这一层」某一行上松手 = 把这一格记给那一行。
    // （以前要按住 350ms 不动才算抓起，可人拖东西就是"按下就拖"，一移动长按就被
    //  自己取消，松手什么都不发生 —— 用户 2026-10-31 "无法通过拖动给清单里的东西
    //  添加坐标"。长按只留给"画路线"，见 `routeLayer.onLongPressed`。）
    //
    // **不走 QDrag**（用户 2026-10-31："不能通过拖动加资源"，之前 Drag.Automatic
    // 起不来/拖不动）：改成 QML **定时轮询光标**（`controller.cursorState()`），
    // 松手时问一下各扇「这一层」小窗：光标底下是哪一行 → 直接把这一格记给那一行。
    // 好处：跨窗口不依赖平台拖放会话，无头环境也能测。
    property int dragRow: -1
    property int dragCol: -1
    property bool dragging: false
    // 这一拖要记哪几格（起手时定下来）：**Ctrl 勾上的 + 抓着的这一格**
    property var dragCells: []

    function hasCell(cells, row, col) {
        for (var i = 0; i < (cells || []).length; i++) {
            var one = cells[i] || ({})
            if (Number(one.row) === Number(row)
                    && Number(one.col) === Number(col))
                return true
        }
        return false
    }

    function beginCellDrag(row, col) {
        panel.dragRow = Number(row)
        panel.dragCol = Number(col)
        // 这一拖记**勾上的 + 抓着的**：Ctrl+点多选就是"一次记好几个坐标"，
        // 抓的那一格没勾也并进来 —— 拖一下就把勾选丢掉太冤（也免得"勾了 3 格
        // 却只记了 1 格"）。落格清勾选由 `gridAssignMany` 那一处管。
        var cells = []
        var multi = panel.host.gridMulti || []
        for (var i = 0; i < multi.length; i++) {
            var one = multi[i] || ({})
            cells.push({ "row": Number(one.row), "col": Number(one.col) })
        }
        if (!panel.hasCell(cells, panel.dragRow, panel.dragCol))
            cells.push({ "row": panel.dragRow, "col": panel.dragCol })
        panel.dragCells = cells
        panel.dragging = true
        // 正在拖的那一格在图上画个实框（`GridLayer` 里本来就有这条画法，
        // 以前没人给它赋值，等于一直是死代码）；勾着的那些格子照旧是细框
        panel.host.gridDrag = { "row": panel.dragRow, "col": panel.dragCol }
        // 起手就给一句提示 + 记一行日志：不然"没反应"时什么都查不到。
        // 格数写在**最前面**：底栏窄，后半截会被省略号吃掉，而"这次记几格"正是
        // 拖多选时最要紧的那一句。
        panel.host.mapHint = cells.length > 1
                ? "记 " + cells.length + " 格 · 松手落在怪/资源行上"
                : "松手落在「这一层」的怪/资源行上"
        if (controller)
            controller.uiNote("ui.cell_drag_start",
                              String(panel.host.mapFloor) + " " + row + "," + col
                              + " 共 " + cells.length + " 格")
    }

    // 松开时光标底下是哪一格（13×13 之外 = `{}`）。走格子层那条规则，不另写一份。
    function cellUnderGlobal(globalX, globalY) {
        var at = gridLayer.mapFromGlobal(Number(globalX), Number(globalY))
        return gridLayer.cellAt(at.x, at.y)
    }

    function rowAtGlobal(globalX, globalY) {
        var names = panel.host.floorWindows || []
        for (var i = 0; i < names.length; i++) {
            var sheet = panel.host.floorSheetOf(String(names[i] || ""))
            if (!sheet)
                continue
            var hit = sheet.rowAt(Number(globalX), Number(globalY))
            if (hit)
                return hit
        }
        return null
    }

    function tickCellDrag() {
        if (!panel.dragging)
            return
        var state = controller ? controller.cursorState() : null
        if (!state || state.length < 3) {
            panel.dragging = false
            panel.host.gridDrag = ({})
            if (controller)
                controller.uiNote("ui.cell_drag_end", "no_cursor")
            return
        }
        var down = !!state[2]
        if (down)
            return
        panel.dragging = false
        panel.host.gridDrag = ({})
        var hit = panel.rowAtGlobal(Number(state[0]), Number(state[1]))
        // 松手还在抓起的那一格上 = 只是**点了一下**（选中这一格，由 `tapped` 管），
        // 不是拖失败：别记坐标，也别弹"没有行"红字
        var here = panel.cellUnderGlobal(Number(state[0]), Number(state[1]))
        var sameCell = here.row === panel.dragRow && here.col === panel.dragCol
        if (controller)
            controller.uiNote("ui.cell_drag_end",
                              (hit ? "hit " : (sameCell ? "tap " : "miss "))
                              + Number(state[0]) + "," + Number(state[1]))
        if (hit) {
            panel.host.assignCellToRow(hit, panel.dragCells)
            panel.host.mapHint = ""      // 记上了就把那句提示收掉
        } else if (!sameCell) {
            panel.host.mapHint = "松开的地方没有行：拖到「这一层」的怪/资源行上再松手"
        } else {
            panel.host.mapHint = ""      // 点了一下：起手那句提示也收掉
        }
        panel.dragCells = []
    }

    Timer {
        objectName: "cellDragTimer"
        interval: 40
        repeat: true
        running: panel.dragging
        onTriggered: panel.tickCellDrag()
    }

    // 点地图上的空白：把开着的输入框收起来并生效
    // （用户 2026-10-31："粘贴完坐标怎么点空白不退出"）
    MouseArea {
        objectName: "mapBlankTap"
        anchors.fill: parent
        z: 900
        visible: panel.openField !== null
        onClicked: function (mouse) {
            var field = panel.openField
            if (field) {
                var at = mapToItem(null, mouse.x, mouse.y)
                var box = field.mapToItem(null, 0, 0, field.width, field.height)
                if (at.x >= box.x - 8 && at.x <= box.x + Math.max(box.width, 96) + 8
                        && at.y >= box.y - 8 && at.y <= box.y + box.height + 8)
                    return
            }
            panel.closeEditors()
        }
    }

    // 输入框全收掉（点空白 / 切层时都走这里）
    function closeEditors() {
        panel.closeTick++
    }
}
