import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
// 配色/按钮在上一层（docs/UI_MAP.md）
import ".."
import "../shared"
// 它自己的下拉菜单（一个界面一个文件夹）
import "pick_menu"

// 「这一层」小窗：这一层有什么怪、哪些资源、哪几个楼梯，各几个、记在哪几格；
// 就地改数量、勾掉打过的、写备忘。
//
// 2026-11-02 重新设计（用户："不合理的东西和交互太多了"）：
//   · 一个窗口一次只摆一类：页签「怪物｜资源｜楼梯」，每类一张白卡，不再摞着滚；
//   · 标题行 = 层名 + 「标位置中」小章 + ‹ ›（上/下一层）+ ⋯（刷新 / 标位置 / 删除本层）+ ✕；
//     原来底栏的「完成」去掉（改动每一下都即时落库，✕ / Esc 关窗）；
//   · 每一行高度固定，「位置」不再在编辑模式里多冒一行，而是行尾一个胶囊
//     （「未标」/「2 格」，点它 = 选中这个词条，地图上圈出它的格子）；
//     选中的词条的坐标写在窗口底部那条「已选」里，可以一键复制；
//   · 楼梯的缩略图不再响应点击（原来点它悄悄把上楼换成下楼）：方向是明写着字的
//     「上楼 | 下楼」二选一；
//   · 备忘固定在窗口底部，随时可见。
//
// **这里不画地图**：截图、路线层、坐标系、对比高亮、楼梯都在主界面的地图那一栏
// （views/map_view/MapPanel.qml）；这扇窗只管清单。
//
// 它是**一扇真窗口**（无边框 + Qt.Tool，置顶跟着主窗口开关）：能拖到桌面任何地方、能多开
// （每层一个），所以和主面板各一份文件（docs/UI_MAP.md 第 2 项）。
//
// 状态不在这儿：名字、位置、拉过的尺寸都在主窗口的 `floorWindows` /
// `floorPositions` / `floorSizes` 上；这里读 `host.xxx`，`host` = 主窗口
// （MainWindow.qml 里写 `FloorSheetWindow { host: win }`）。
// 四边八角的拉伸手柄 `SheetGrip` 就在下面 —— 只有这扇窗用，不往 components 里放。
Window {
    id: sheetRoot
    // 主窗口（原来直接叫 win）
    property var host

    objectName: "floorSheetWindow"
    // 删本层的两步确认（在「⋯」菜单里）
    property bool deleteArm: false
    property string sheetName: ""
    // 现在看的是哪一页："mon" / "item" / "stair"
    property string tab: "mon"

    // ---- 拖动"抓一格"时：光标落在哪一行上？----

    // 光标（**全局坐标**）落在哪一行上？返回 `{kind, index, name, effect}`；
    // 不在任何一行上返回 null。只认**看得见的**行（别的页签里的行不接）。
    // 用场景坐标比较：把全局坐标减去窗口位置，行自己给的 `mapToItem(null, …)` 也是场景坐标。
    function rowAt(globalX, globalY) {
        var x = Number(globalX) - sheetRoot.x
        var y = Number(globalY) - sheetRoot.y
        var kinds = [["floorMonRow", "monster"], ["floorItemRow", "item"]]
        for (var k = 0; k < kinds.length; k++) {
            var rows = []
            collectRows(sheetRoot.contentItem, kinds[k][0], rows)
            for (var i = 0; i < rows.length; i++) {
                var row = rows[i]
                if (!row.visible)
                    continue
                var box = row.mapToItem(null, 0, 0)
                if (x < box.x || x > box.x + row.width
                        || y < box.y || y > box.y + row.height)
                    continue
                var kind = kinds[k][1]
                if (kind === "monster") {
                    // 怪那一行的委托上有个 `mon`（= modelData），名字从它取；
                    // 直接读 modelData 在委托里拿不到（实测拿到空名字）
                    var mon = row.mon || ({})
                    return { "kind": "monster", "index": Number(row.rowIndex),
                             "name": String(mon.name || ""), "effect": "" }
                }
                return { "kind": "item", "index": Number(row.rowIndex),
                         "name": String(row.itemName || ""),
                         "effect": String(row.item ? row.item.effect : "") }
            }
        }
        return null
    }

    function collectRows(item, name, out) {
        if (!item)
            return out
        var list = item.children || []
        for (var i = 0; i < list.length; i++) {
            var child = list[i]
            if (!child)
                continue
            if (child.objectName === name)
                out.push(child)
            collectRows(child, name, out)
        }
        return out
    }

    // 拖着一格从地图上过来时，光标底下是哪一行（"monster:0" / "item:2" / ""）：
    // 那一行整行变淡蓝并写「放到这里」。地图那边是轮询光标（`controller.cursorState()`）
    // 松手的，所以这里也轮询同一个来源。
    property string dropKey: ""
    readonly property bool dragging: ((host.gridDrag || ({})).row !== undefined)
    Timer {
        interval: 40
        repeat: true
        running: sheetRoot.visible && sheetRoot.dragging
        onTriggered: {
            var state = controller ? controller.cursorState() : null
            var hit = (state && state.length >= 3)
                      ? sheetRoot.rowAt(Number(state[0]), Number(state[1])) : null
            sheetRoot.dropKey = hit ? (hit.kind + ":" + hit.index) : ""
        }
    }
    onDraggingChanged: if (!sheetRoot.dragging) sheetRoot.dropKey = ""

    // 点窗口空白时加一：所有开着的输入框收到就各自收起来并生效
    // （用户 2026-10-31："粘贴完坐标怎么点空白不退出"）
    property int closeTick: 0
    // 现在开着的那一格（点别处就收起来；点在它自己身上不算）
    property var openField: null

    MouseArea {
        objectName: "sheetBlankTap"
        anchors.fill: parent
        z: 900
        visible: sheetRoot.openField !== null
        onClicked: function (mouse) {
            var field = sheetRoot.openField
            if (field) {
                // 输入框比那一格宽，可点范围按"它自己的宽度"算，别一碰就收
                var at = mapToItem(null, mouse.x, mouse.y)
                var box = field.mapToItem(null, 0, 0, field.width, field.height)
                var right = box.x + Math.max(box.width, 96) + 8
                if (at.x >= box.x - 8 && at.x <= right
                        && at.y >= box.y - 8 && at.y <= box.y + box.height + 8)
                    return
            }
            sheetRoot.closeTick++
        }
    }

    // ---- 这一层的三份清单（都跟着层记录变）----
    readonly property var monList: {
        if (controller)
            controller.mapHistory     // 绑一下：改了会重列
        return host.sheetMons(sheetRoot.sheetName)
    }
    // 资源按习惯顺序显示（用户："资源怎么不按习惯排序"）：顺序由 Python 算
    readonly property var itemList: {
        if (!controller)
            return []
        controller.mapHistory
        return controller.sortedSheetItems(sheetRoot.sheetName)
    }
    readonly property var stairList: host.stairRows(sheetRoot.sheetName)

    // ---- 标位置模式（打开清单就自动进，地图那边的「编辑」按钮同一个开关）----
    // 只有这一层在编辑时才开（主窗口的 gridEditOn/Floor 是全局一份）
    readonly property bool gridEditActive:
        host.gridEditOn && host.gridEditFloor === sheetRoot.sheetName

    // 这个词条在这一层标过哪几格 → `[{row, col}]`（0 开始）
    function posList(name, effect) {
        if (controller)
            controller.mapHistory     // 绑一下：格子改了要重取
        return host.gridPositionsFor(sheetRoot.sheetName, String(name || ""),
                                     String(effect || ""))
    }

    // 行尾胶囊上写的字：标过几格（1 开始的行列都在底部「已选」那条里）
    function posChipText(name, effect) {
        var count = sheetRoot.posList(name, effect).length
        return count > 0 ? (count + " 格") : "未标"
    }

    // 底部「已选」那条：选中的词条 + 它的每一格（"6,6 · 3,4"，1 开始）
    readonly property string selectedName: String(host.gridSelected || "")
    function selectedCells() {
        var cells = sheetRoot.posList(sheetRoot.selectedName, "")
        var parts = []
        for (var i = 0; i < cells.length; i++)
            parts.push((Number(cells[i].row) + 1) + "," + (Number(cells[i].col) + 1))
        return parts
    }

    visible: false
    color: "transparent"
    // 置顶跟着主窗口的「置顶」开关走（切换那一下 Qt 会重建这扇窗的原生窗口）。
    // 不用 transientParent 挂在主窗口名下：从属窗口拿不到键盘焦点，输入框打不了字。
    flags: Qt.FramelessWindowHint | Qt.Tool
           | (host && host.pinned ? Qt.WindowStaysOnTopHint : 0)
    // 这扇窗是主窗口开的（测试按它把"自己开的窗"挑出来）
    property var ownerWindow: host
    // 能放多大、能拖到哪，由**屏幕**说话（以前是按主窗口算的）。
    // Window.screen 是 QQuickScreenInfo：只有 width/height（没有
    // availableGeometry），底部再留 56 给任务栏，别让手柄压在下面。
    readonly property var screenRect: {
        var scr = sheetRoot.screen
        if (!scr)
            return Qt.rect(0, 0, 1920, 1080)
        var originX = scr.virtualX !== undefined ? scr.virtualX : 0
        var originY = scr.virtualY !== undefined ? scr.virtualY : 0
        return Qt.rect(originX, originY, scr.width, scr.height)
    }
    // 窗口最外圈留给投影的透明边；灰底卡片（cardBox）画在它里面，和主窗口同一套
    readonly property int inset: Theme.windowInset
    // 灰底卡片里自上而下：标题行 / 页签行 / 白卡（清单）/ 已选条（有才占）/ 备忘行
    readonly property int headH: 34
    readonly property int tabsH: 34
    readonly property int stripH: 28
    readonly property int memoH: 32
    readonly property int gap: 8
    // 一行多高 / 列表里缩略图边长：怪物行、资源行**同一条规矩**
    readonly property int rowH: 32
    readonly property int thumbSide: 22
    // 数量框的宽（含右边那两个箭头）：一个数字 + 两个箭头，别留一大截空白
    readonly property int countBoxW: 34
    // 行尾位置胶囊的宽
    readonly property int chipW: 54
    readonly property int minW: 280
    readonly property int minH: 280
    readonly property int maxW: Math.max(minW, screenRect.width - 16)
    readonly property int maxH: Math.max(minH, screenRect.height - 56)
    // 没拉过大小时的默认大小：一页清单放得下，不用先滚
    readonly property int autoW: 330
    readonly property int autoH: 2 * inset + 380

    // 窗口大小跟着卡片走：拉过大就按拉的，没拉过按默认
    width: Math.round(cardBox.sized
                      ? Math.max(minW, Math.min(maxW, cardBox.wantedW))
                      : autoW)
    height: Math.round(cardBox.sized
                       ? Math.max(minH, Math.min(maxH, cardBox.wantedH))
                       : Math.min(maxH, autoH))
    // 整块钳在屏幕里：拖到屏幕边上就停住，但**不能**把越界的那截攒着 ——
    // 攒着的话往回拖要先"还债"，窗口会卡住/跳（用户："一直在抖动"）。
    // 边也要钳：不然拉大以后右下角的拉大手柄会跑到屏幕外点不到。
    // 卡片贴屏幕边就算到头：外圈 10px 透明投影边可以伸出屏幕。
    function clampPos() {
        var rect = sheetRoot.screenRect
        if (!rect)
            return
        var left = rect.x + 2 - sheetRoot.inset
        var top = rect.y + 2 - sheetRoot.inset
        var right = Math.max(left, rect.x + rect.width - sheetRoot.width - 2
                                   + sheetRoot.inset)
        var bottom = Math.max(top, rect.y + rect.height - sheetRoot.height - 2
                                   + sheetRoot.inset)
        sheetRoot.x = Math.round(Math.max(left, Math.min(sheetRoot.x, right)))
        sheetRoot.y = Math.round(Math.max(top, Math.min(sheetRoot.y, bottom)))
    }

    // 换到上一层 / 下一层：就在这个位置开那一层的清单，再把这一扇关掉
    // （不再多开一扇窗，也不再有那个看不懂的「＋」）
    function goFloor(delta) {
        var next = host.adjacentFloor(sheetRoot.sheetName, delta)
        if (next === "")
            return
        var spots = {}
        for (var key in host.floorPositions)
            spots[key] = host.floorPositions[key]
        spots[next] = { "x": sheetRoot.x, "y": sheetRoot.y }
        host.floorPositions = spots
        host.openFloorSheet(next)
        host.closeFloorSheet(sheetRoot.sheetName)
    }

    // 按 Esc 关这一扇（焦点在哪个窗口上，事件就到哪个窗口）；「⋯」菜单开着时 Esc 先关菜单
    Shortcut {
        sequence: "Esc"
        enabled: !moreMenu.opened
        onActivated: host.closeFloorSheet(sheetRoot.sheetName)
    }
    // 点了别处（比如主窗口）：正在开的下拉菜单收起来
    onActiveChanged: {
        if (!sheetRoot.active && host.pickMode !== ""
            && String(host.pickFloor) === sheetRoot.sheetName)
            host.pickMode = ""
    }

    // 窗口投影：和主窗口同一套（灰底卡片 + 软阴影）
    WindowShadow {
        anchors.fill: cardBox
        radius: cardBox.radius
    }

    Rectangle {
        id: cardBox
        objectName: "floorCard"
        anchors.fill: parent
        anchors.margins: sheetRoot.inset
        // 用户拉过大小没有（拉过就按拉的来，没拉过就按默认）
        readonly property bool sized:
            host.floorSizes[sheetRoot.sheetName] !== undefined
        readonly property real wantedW: Math.max(sheetRoot.minW, Math.min(
            sheetRoot.maxW, host.floorW(sheetRoot.sheetName, sheetRoot.autoW)))
        readonly property real wantedH: Math.max(sheetRoot.minH, Math.min(
            sheetRoot.maxH, host.floorH(sheetRoot.sheetName,
                                        sheetRoot.autoH - 2 * sheetRoot.inset)))
        radius: 10
        color: Theme.canvas
        clip: true
        MouseArea { anchors.fill: parent }

        // 一页页签的小药丸：选中的那页蓝底蓝字，字后面跟着有几条
        component TabPill: Rectangle {
            id: pill
            property string key: ""
            property string label: ""
            property int count: 0
            readonly property bool current: sheetRoot.tab === pill.key
            height: 26
            radius: 13
            width: pillText.implicitWidth + 24
            color: pill.current ? Theme.accentSoft
                 : (pillMouse.containsMouse ? Theme.hover : "transparent")
            Text {
                id: pillText
                anchors.centerIn: parent
                text: pill.label + (pill.count > 0 ? "  " + pill.count : "")
                color: pill.current ? Theme.accent : Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 12
                font.bold: pill.current
            }
            MouseArea {
                id: pillMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sheetRoot.tab = pill.key
            }
        }

        // 勾选框（打过 / 拿过）：灰框空心 = 没打；蓝底白勾 = 打过了
        component DoneBox: Rectangle {
            id: box
            property bool checked: false
            signal toggled()
            width: 16
            height: 16
            radius: 4
            color: box.checked ? Theme.accent : "transparent"
            border.width: 1
            border.color: box.checked ? Theme.accent : Theme.fieldEdge
            Text {
                anchors.centerIn: parent
                visible: box.checked
                text: "✓"
                color: Theme.accentInk
                font.pixelSize: 11
                font.bold: true
            }
            MouseArea {
                anchors.fill: parent
                anchors.margins: -5
                cursorShape: Qt.PointingHandCursor
                onClicked: box.toggled()
            }
        }

        // 行尾位置胶囊：「未标」/「2 格」；点它 = 选中这个词条（图上圈出它的格子）；
        // 拖着格子经过这一行时写「放到这里」
        component PosChip: Rectangle {
            id: chip
            property string name: ""
            property string effect: ""
            property bool dropping: false
            readonly property bool picked: sheetRoot.selectedName === chip.name
                                           && chip.name !== ""
            height: 20
            radius: 10
            width: sheetRoot.chipW
            color: chip.dropping || chip.picked ? Theme.accentSoft : Theme.chip
            Text {
                id: chipText
                objectName: "chipText"
                anchors.centerIn: parent
                text: chip.dropping ? "放到这里"
                      : sheetRoot.posChipText(chip.name, chip.effect)
                color: chip.dropping || chip.picked ? Theme.accent : Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 10
                font.bold: chip.picked
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: host.gridSelect(chip.name)
            }
        }

        // ---- 标题行：可以拖着走 ----
        Item {
            id: header
            x: sheetRoot.gap
            y: 0
            width: cardBox.width - 2 * sheetRoot.gap
            height: sheetRoot.headH

            MouseArea {
                id: sheetDrag
                anchors.fill: parent
                property real pressX: 0
                property real pressY: 0
                property real startX: 0
                property real startY: 0
                cursorShape: pressed ? Qt.ClosedHandCursor
                                     : Qt.ArrowCursor
                // 窗口自己在动，只能用**屏幕坐标**：用窗口内坐标算出来的
                // 位移会越来越小（实测拖 220px 只挪了 110px）
                onPressed: function (m) {
                    var at = mapToGlobal(m.x, m.y)
                    pressX = at.x
                    pressY = at.y
                    startX = sheetRoot.x
                    startY = sheetRoot.y
                }
                onPositionChanged: function (m) {
                    if (!pressed)
                        return
                    var at = mapToGlobal(m.x, m.y)
                    // 每步都钳住：拖到屏幕边上就停在那儿，往回拖立刻跟着走
                    sheetRoot.x = Math.round(startX + (at.x - pressX))
                    sheetRoot.y = Math.round(startY + (at.y - pressY))
                    sheetRoot.clampPos()
                }
                onReleased: host.saveFloorPos(sheetRoot.sheetName,
                                             sheetRoot.x,
                                             sheetRoot.y)
            }

            Text {
                objectName: "floorTitle"
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.right: headRight.left
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                text: sheetRoot.sheetName
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 14
                font.bold: true
                elide: Text.ElideRight
            }

            Row {
                id: headRight
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                // 现在在标位置：不用猜"为什么地图上多了一层坐标线"
                Chip {
                    objectName: "floorEditBadge"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: sheetRoot.gridEditActive
                    tone: "accent"
                    text: "标位置中"
                }
                IconBtn {
                    objectName: "floorPrev"
                    glyph: "‹"
                    glyphSize: 16
                    opacity: host.adjacentFloor(sheetRoot.sheetName, -1) !== ""
                             ? 1.0 : 0.3
                    onClicked: sheetRoot.goFloor(-1)
                }
                IconBtn {
                    objectName: "floorNext"
                    glyph: "›"
                    glyphSize: 16
                    opacity: host.adjacentFloor(sheetRoot.sheetName, 1) !== ""
                             ? 1.0 : 0.3
                    onClicked: sheetRoot.goFloor(1)
                }
                IconBtn {
                    id: moreBtn
                    objectName: "floorMenuBtn"
                    glyph: "⋯"
                    glyphSize: 15
                    onClicked: moreMenu.open()
                }
                IconBtn {
                    id: sheetClose
                    objectName: "floorClose"
                    glyph: "✕"
                    glyphSize: 12
                    hoverInk: Theme.danger
                    hoverBack: Theme.dangerSoft
                    onClicked: host.closeFloorSheet(sheetRoot.sheetName)
                }
            }
        }

        // ---- 页签行：怪物 5｜资源 7｜楼梯 2          ＋ 加…（跟着页签变）----
        Item {
            id: tabsRow
            x: sheetRoot.gap
            y: sheetRoot.headH
            width: cardBox.width - 2 * sheetRoot.gap
            height: sheetRoot.tabsH

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                TabPill {
                    objectName: "floorTabMon"
                    key: "mon"
                    label: "怪物"
                    count: sheetRoot.monList.length
                }
                TabPill {
                    objectName: "floorTabItem"
                    key: "item"
                    label: "资源"
                    count: sheetRoot.itemList.length
                }
                TabPill {
                    objectName: "floorTabStair"
                    key: "stair"
                    label: "楼梯"
                    count: sheetRoot.stairList.length
                }
            }

            FlatBtn {
                id: addMonBtn
                objectName: "floorAddMon"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: sheetRoot.tab === "mon"
                label: "＋ 加怪"
                onClicked: host.openPickMenu("mon", sheetRoot.sheetName,
                                             addMonBtn, -1, sheetRoot)
            }
            FlatBtn {
                id: addItemBtn
                objectName: "floorAddItem"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: sheetRoot.tab === "item"
                label: "＋ 加资源"
                onClicked: host.openPickMenu("item", sheetRoot.sheetName,
                                             addItemBtn, -1, sheetRoot)
            }
            // 楼梯：方向在行里切、位置拖上去（或粘坐标）、目标层打层号；这里只加一行
            FlatBtn {
                objectName: "floorAddStair"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: sheetRoot.tab === "stair"
                label: "＋ 加楼梯"
                onClicked: host.addStairRow(sheetRoot.sheetName, "up")
            }
        }

        // ---- 窗口底部：已选条（选中词条时才有）+ 备忘（一直在）----
        Item {
            id: bottomBlock
            x: sheetRoot.gap
            width: cardBox.width - 2 * sheetRoot.gap
            anchors.bottom: parent.bottom
            anchors.bottomMargin: sheetRoot.gap
            readonly property bool stripShown:
                sheetRoot.gridEditActive && sheetRoot.selectedName !== ""
            height: sheetRoot.memoH
                    + (stripShown ? sheetRoot.stripH + 6 : 0)

            // 已选：「红头怪  6,6 · 3,4」+ 复制
            Rectangle {
                id: strip
                objectName: "floorSelectedStrip"
                visible: bottomBlock.stripShown
                width: parent.width
                height: sheetRoot.stripH
                radius: Theme.radius
                color: Theme.accentSoft
                Text {
                    objectName: "floorSelectedText"
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.right: copyBtn.left
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    readonly property var cells: sheetRoot.selectedCells()
                    text: "已选：" + sheetRoot.selectedName + "   "
                          + (cells.length > 0 ? cells.join(" · ") : "还没标位置")
                    color: Theme.accent
                    font.family: Theme.uiFont
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
                TextBtn {
                    id: copyBtn
                    objectName: "floorSelectedCopy"
                    pill: true
                    anchors.right: parent.right
                    anchors.rightMargin: 4
                    anchors.verticalCenter: parent.verticalCenter
                    text: "复制"
                    accent: Theme.accent
                    visible: sheetRoot.selectedCells().length > 0
                    onClicked: {
                        var cells = sheetRoot.selectedCells()
                        controller.clipboardCopy(
                            sheetRoot.selectedName + " "
                            + host.floorShort(sheetRoot.sheetName) + "层 "
                            + cells.join(" / "))
                    }
                }
            }

            // 备忘：每扇窗自己带出这一层的备忘（唯一会跨重启的自由文本）
            Item {
                anchors.bottom: parent.bottom
                width: parent.width
                height: sheetRoot.memoH
                Text {
                    id: memoLabel
                    anchors.left: parent.left
                    anchors.leftMargin: 4
                    anchors.verticalCenter: parent.verticalCenter
                    text: "备忘"
                    color: Theme.ink2
                    font.family: Theme.uiFont
                    font.pixelSize: 12
                    font.bold: true
                }
                Rectangle {
                    anchors.left: memoLabel.right
                    anchors.leftMargin: 10
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    height: Theme.controlH
                    radius: Theme.radius
                    anchors.verticalCenter: parent.verticalCenter
                    color: memoField.activeFocus ? Theme.paper : Theme.tile
                    border.width: 1
                    border.color: memoField.activeFocus ? Theme.accent
                                                        : Theme.hairline
                    TextField {
                        id: memoField
                        objectName: "floorMemo"
                        anchors.fill: parent
                        anchors.leftMargin: 6
                        anchors.rightMargin: 6
                        verticalAlignment: TextInput.AlignVCenter
                        background: null
                        color: Theme.ink
                        font.family: Theme.uiFont
                        font.pixelSize: 11
                        selectByMouse: true
                        placeholderText: "这一层的备忘"
                        placeholderTextColor: Theme.ink3
                        text: host.sheetMemo(sheetRoot.sheetName)
                        onEditingFinished: controller.saveFloorMemo(
                            sheetRoot.sheetName, text)
                    }
                }
            }
        }

        // ---- 清单：一页一类，放在一张白卡里 ----
        Card {
            id: listCard
            x: sheetRoot.gap
            y: sheetRoot.headH + sheetRoot.tabsH
            width: cardBox.width - 2 * sheetRoot.gap
            height: Math.max(60, cardBox.height - y - bottomBlock.height
                                 - 2 * sheetRoot.gap)
            pad: sheetRoot.gap

            Flickable {
                id: sheetFlick
                objectName: "floorFlick"
                width: parent.width
                height: listCard.height - 2 * listCard.pad
                contentWidth: width
                contentHeight: sheetBody.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: sheetBody
                    width: sheetFlick.width
                    spacing: 0

                    // ============ 怪物 ============
                    Column {
                        id: monPage
                        width: parent.width
                        visible: sheetRoot.tab === "mon"

                        Text {
                            objectName: "floorMonEmpty"
                            width: parent.width
                            height: visible ? 40 : 0
                            visible: sheetRoot.monList.length === 0
                            verticalAlignment: Text.AlignVCenter
                            text: "这一层还没有怪。点右上「＋ 加怪」从手册里挑。"
                            color: Theme.ink3
                            font.family: Theme.uiFont
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                        }

                        Repeater {
                            model: sheetRoot.monList
                            delegate: Item {
                                id: monRow
                                objectName: "floorMonRow"
                                width: parent.width
                                height: sheetRoot.rowH

                                readonly property var mon: modelData || ({})
                                // 委托里的 `index` 只是上下文属性，别的代码（rowAt）读不到，要单独露一份
                                readonly property int rowIndex: index
                                readonly property string monIcon: host.hasUrl(mon.icon)
                                    ? String(mon.icon)
                                    : host.monsterIconNamed(mon.name)
                                // 拖着格子经过这一行（轮询光标）/ 真拖拽会话经过
                                readonly property bool dropping:
                                    monDrop.containsDrag
                                    || sheetRoot.dropKey === ("monster:" + index)

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.topMargin: 1
                                    anchors.bottomMargin: 1
                                    radius: Theme.radius
                                    color: monRow.dropping ? Theme.accentSoft
                                         : (monHover.hovered ? Theme.tile
                                                             : "transparent")
                                }
                                HoverHandler { id: monHover }

                                Row {
                                    anchors.fill: parent
                                    anchors.leftMargin: 4
                                    spacing: 6

                                    DoneBox {
                                        objectName: "floorMonDone"
                                        anchors.verticalCenter: parent.verticalCenter
                                        checked: !!monRow.mon.done
                                        onToggled: controller.toggleFloorMonsterDone(
                                            sheetRoot.sheetName, index)
                                    }

                                    Rectangle {
                                        objectName: "floorMonThumb"
                                        width: sheetRoot.thumbSide
                                        height: sheetRoot.thumbSide
                                        radius: 4
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: Theme.tile
                                        clip: true
                                        Image {
                                            id: monThumb
                                            objectName: "floorMonThumbImage"
                                            anchors.fill: parent
                                            anchors.margins: 2
                                            source: monRow.monIcon
                                            // 图打不开（比如上次读手册的临时图被清了）
                                            // 就别留个空洞：按状态显示，退回首字
                                            visible: status === Image.Ready
                                            fillMode: Image.PreserveAspectFit
                                            smooth: false
                                        }
                                        Text {
                                            anchors.centerIn: parent
                                            visible: monThumb.status !== Image.Ready
                                            text: monRow.mon.name
                                                  ? monRow.mon.name.charAt(0) : "?"
                                            color: Theme.ink3
                                            font.family: Theme.uiFont
                                            font.pixelSize: 11
                                        }
                                    }

                                    // 怪名**只读**（用户 2026-10-31："清单界面怪物不需要可以改名"）：
                                    // 名字来自手册/模板，是这只怪的身份，能改就和记录对不上；
                                    // 要换成别的怪就重新「＋ 加怪」挑一只。
                                    Text {
                                        objectName: "floorMonName"
                                        width: parent.width - 4 - 16 - 22
                                               - sheetRoot.countBoxW - sheetRoot.chipW
                                               - 18 - 6 * 5
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: monRow.mon.name || ""
                                        color: Theme.ink
                                        font.family: Theme.uiFont
                                        font.pixelSize: 12
                                        elide: Text.ElideRight
                                    }

                                    NumberStepper {
                                        width: sheetRoot.countBoxW
                                        anchors.verticalCenter: parent.verticalCenter
                                        fieldName: "floorMonCount"
                                        text: monRow.mon.count === undefined
                                              ? "" : String(monRow.mon.count)
                                        onCommitted: function (value) {
                                            controller.saveFloorMonsterField(
                                                sheetRoot.sheetName, index,
                                                "count", value)
                                        }
                                    }

                                    PosChip {
                                        objectName: "floorMonPos"
                                        anchors.verticalCenter: parent.verticalCenter
                                        name: String(monRow.mon.name || "")
                                        dropping: monRow.dropping
                                    }

                                    // 删这一只：平时淡着，鼠标在这一行上才亮（不是一碰就删的黑字）
                                    Text {
                                        objectName: "floorMonDelete"
                                        width: 18
                                        height: 18
                                        anchors.verticalCenter: parent.verticalCenter
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        text: "✕"
                                        opacity: monHover.hovered ? 1.0 : 0.35
                                        color: delMonMouse.containsMouse
                                               ? Theme.danger : Theme.ink3
                                        font.pixelSize: 11
                                        MouseArea {
                                            id: delMonMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: controller.removeFloorMonster(
                                                sheetRoot.sheetName, index)
                                        }
                                    }
                                }

                                DropArea {
                                    id: monDrop
                                    anchors.fill: parent
                                    keys: ["application/x-grid-cell"]
                                    onDropped: function (drop) {
                                        var data = JSON.parse(
                                            drop.getDataAsString("application/x-grid-cell"))
                                        var cells = (data.cells && data.cells.length)
                                                ? data.cells : [data]
                                        // 名字先拿住：落格会重建这一行，循环里再读就是空
                                        host.gridAssignMany(cells, "monster",
                                                            String(monRow.mon.name || ""))
                                    }
                                }
                            }
                        }
                    }

                    // ============ 资源 ============
                    Column {
                        id: itemPage
                        width: parent.width
                        visible: sheetRoot.tab === "item"

                        Text {
                            objectName: "floorItemEmpty"
                            width: parent.width
                            height: visible ? 40 : 0
                            visible: sheetRoot.itemList.length === 0
                            verticalAlignment: Text.AlignVCenter
                            text: "这一层还没有资源。点右上「＋ 加资源」。"
                            color: Theme.ink3
                            font.family: Theme.uiFont
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                        }

                        Repeater {
                            model: sheetRoot.itemList
                            delegate: Item {
                                id: itemRow
                                objectName: "floorItemRow"
                                width: parent.width
                                // 一行 32；点开效果就多一块数字框（黄宝石三段，会长高）
                                height: sheetRoot.rowH
                                        + (itemRow.expanded ? effectEditor.implicitHeight + 8 : 0)

                                readonly property var item: modelData || ({})
                                readonly property int rowIndex: index
                                readonly property string itemName: String(item.name || "")
                                property bool expanded: false
                                readonly property var partList: controller
                                    ? controller.itemEffectPartList(item.effect || "") : []
                                // 效果一句话：「攻击力 +1 · 防御力 +1」
                                readonly property string effectLine: {
                                    var out = []
                                    for (var i = 0; i < partList.length; i++) {
                                        var one = partList[i] || ({})
                                        out.push(String(one.label || "") + " "
                                                 + String(one.sign || "")
                                                 + String(one.digits || ""))
                                    }
                                    return out.length > 0 ? out.join("  ·  ")
                                                          : String(item.effect || "")
                                }
                                readonly property bool dropping:
                                    itemDrop.containsDrag
                                    || sheetRoot.dropKey === ("item:" + index)

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.topMargin: 1
                                    anchors.bottomMargin: 1
                                    radius: Theme.radius
                                    color: itemRow.dropping ? Theme.accentSoft
                                         : (itemHover.hovered ? Theme.tile
                                                              : "transparent")
                                }
                                HoverHandler { id: itemHover }

                                Row {
                                    id: itemTop
                                    x: 4
                                    height: sheetRoot.rowH
                                    width: parent.width - 4
                                    spacing: 6

                                    DoneBox {
                                        objectName: "floorItemDone"
                                        anchors.verticalCenter: parent.verticalCenter
                                        checked: !!itemRow.item.done
                                        onToggled: controller.toggleFloorItemDone(
                                            sheetRoot.sheetName, itemRow.item._src)
                                    }

                                    // 缩略图**代替名字**（用户："不要写什么 X宝石 / X钥匙，
                                    // 用缩略图代替"）。点它换种类（弹出的是挑选菜单，不会悄悄改）
                                    Item {
                                        width: sheetRoot.thumbSide
                                        height: sheetRoot.thumbSide
                                        anchors.verticalCenter: parent.verticalCenter
                                        Image {
                                            id: floorItemIcon
                                            objectName: "floorItemIcon"
                                            anchors.fill: parent
                                            source: host.itemIcon(itemRow.item.icon || "")
                                            visible: status === Image.Ready
                                            fillMode: Image.PreserveAspectFit
                                            smooth: false
                                        }
                                        // 没图（名字对不上道具表 / 临时图被清了）就画个空框 + 首字，
                                        // 别让这一行的图位置空着（用户："资源的缩略图怎么不全"）
                                        Rectangle {
                                            objectName: "floorItemIconFallback"
                                            anchors.fill: parent
                                            radius: 4
                                            color: Theme.tile
                                            visible: floorItemIcon.status !== Image.Ready
                                            Text {
                                                anchors.centerIn: parent
                                                text: itemRow.itemName
                                                      ? itemRow.itemName.charAt(0) : "?"
                                                color: Theme.ink3
                                                font.family: Theme.uiFont
                                                font.pixelSize: 11
                                            }
                                        }
                                        MouseArea {
                                            objectName: "floorItemIconPick"
                                            anchors.fill: parent
                                            anchors.margins: -3
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: host.openPickMenu(
                                                "item", sheetRoot.sheetName,
                                                addItemBtn, itemRow.item._src,
                                                sheetRoot)
                                        }
                                    }

                                    // 效果一句话；点它展开 / 收起数值框
                                    // （用户："宝石加的属性要写死，加的数值要能改"、
                                    //  "黄宝石每个值都要能改"）
                                    Item {
                                        id: effectCell
                                        width: parent.width - 4 - 16 - 22
                                               - sheetRoot.countBoxW - sheetRoot.chipW
                                               - 18 - 6 * 5
                                        height: sheetRoot.rowH
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text {
                                            objectName: "floorItemEffectLine"
                                            anchors.fill: parent
                                            verticalAlignment: Text.AlignVCenter
                                            text: itemRow.effectLine
                                            color: effectMouse.containsMouse
                                                   ? Theme.accent : Theme.ink
                                            font.family: Theme.uiFont
                                            font.pixelSize: 12
                                            elide: Text.ElideRight
                                        }
                                        MouseArea {
                                            id: effectMouse
                                            objectName: "floorItemEffectToggle"
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: itemRow.expanded = !itemRow.expanded
                                        }
                                    }

                                    // 数量：数字框 + 上下箭头（也能直接打字）
                                    NumberStepper {
                                        width: sheetRoot.countBoxW
                                        anchors.verticalCenter: parent.verticalCenter
                                        fieldName: "floorItemCount"
                                        text: itemRow.item.count === undefined
                                              ? "" : String(itemRow.item.count)
                                        onCommitted: function (value) {
                                            controller.saveItemField(
                                                sheetRoot.sheetName, itemRow.item._src,
                                                "count", value)
                                        }
                                    }

                                    PosChip {
                                        objectName: "floorItemPos"
                                        anchors.verticalCenter: parent.verticalCenter
                                        name: itemRow.itemName
                                        effect: String(itemRow.item.effect || "")
                                        dropping: itemRow.dropping
                                    }

                                    Text {
                                        objectName: "floorItemDelete"
                                        width: 18
                                        height: 18
                                        anchors.verticalCenter: parent.verticalCenter
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        text: "✕"
                                        opacity: itemHover.hovered ? 1.0 : 0.35
                                        color: delItemMouse.containsMouse
                                               ? Theme.danger : Theme.ink3
                                        font.pixelSize: 11
                                        MouseArea {
                                            id: delItemMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: controller.removeItem(
                                                sheetRoot.sheetName, itemRow.item._src)
                                        }
                                    }
                                }

                                // 展开后的数值框：一段一条「属性 + 加减号 + 数字框」，
                                // 控件是 shared/EffectEditor.qml，伤害计算那张卡用的是同一个
                                EffectEditor {
                                    id: effectEditor
                                    visible: itemRow.expanded
                                    x: 4 + 16 + 6 + sheetRoot.thumbSide + 6
                                    y: sheetRoot.rowH
                                    width: parent.width - x - 4
                                    fieldName: "floorItemEffect"
                                    parts: itemRow.partList
                                    onPartChanged: function (partIndex, value) {
                                        controller.saveItemEffectPartValue(
                                            sheetRoot.sheetName, itemRow.item._src,
                                            partIndex, value)
                                    }
                                }

                                DropArea {
                                    id: itemDrop
                                    anchors.fill: parent
                                    keys: ["application/x-grid-cell"]
                                    onDropped: function (drop) {
                                        var data = JSON.parse(
                                            drop.getDataAsString("application/x-grid-cell"))
                                        var cells = (data.cells && data.cells.length)
                                                ? data.cells : [data]
                                        // 名字/效果先拿住：落格会重建这一行，循环里再读就是空
                                        host.gridAssignMany(cells, "item",
                                                            String(itemRow.itemName || ""),
                                                            String(itemRow.item.effect || ""))
                                    }
                                }
                            }
                        }
                    }

                    // ============ 楼梯 ============
                    // 用户 2026-10-30："谁告诉你一层只有一个上楼或下楼的？谁告诉你0层就
                    // 一定去1层的？" —— 一行一个楼梯，每行自己带"通哪一层"。
                    // 位置：粘一个坐标，或在图上长按抓一格拖到这行上松手；
                    // 踩到它就切到它记的那一层。
                    Column {
                        id: stairPage
                        width: parent.width
                        visible: sheetRoot.tab === "stair"

                        Text {
                            objectName: "floorStairEmpty"
                            width: parent.width
                            height: visible ? 40 : 0
                            visible: sheetRoot.stairList.length === 0
                            verticalAlignment: Text.AlignVCenter
                            text: "这一层还没有楼梯。点右上「＋ 加楼梯」。"
                            color: Theme.ink3
                            font.family: Theme.uiFont
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                        }

                        Repeater {
                            model: sheetRoot.stairList
                            delegate: Item {
                                id: stairRow
                                objectName: "floorStairRow"
                                required property var modelData
                                width: parent.width
                                // 两行：第一行「方向 → 目标层 ✕」，第二行「本层坐标 / 出口坐标」
                                height: 56

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.topMargin: 2
                                    anchors.bottomMargin: 2
                                    radius: Theme.radius
                                    color: stairHover.hovered ? Theme.tile : "transparent"
                                }
                                HoverHandler { id: stairHover }

                                // 方向：明写着字的二选一（AI 认错方向才点它）。
                                // 缩略图只是装饰，**不响应点击**（原来点它会悄悄换方向）。
                                Row {
                                    x: 6
                                    y: 6
                                    height: 24
                                    spacing: 0
                                    Repeater {
                                        model: [["up", "上楼"], ["down", "下楼"]]
                                        delegate: Rectangle {
                                            objectName: modelData[0] === "up"
                                                        ? "floorStairDirUp"
                                                        : "floorStairDirDown"
                                            readonly property bool on:
                                                String(stairRow.modelData.dir) === modelData[0]
                                            width: 44
                                            height: 24
                                            radius: Theme.radius
                                            color: on ? Theme.accent
                                                      : (dirMouse.containsMouse
                                                         ? Theme.hover : Theme.chip)
                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData[1]
                                                color: on ? Theme.accentInk : Theme.ink2
                                                font.family: Theme.uiFont
                                                font.pixelSize: 11
                                                font.bold: on
                                            }
                                            MouseArea {
                                                id: dirMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    if (!parent.on)
                                                        controller.setStairDirection(
                                                            sheetRoot.sheetName,
                                                            Number(stairRow.modelData.index),
                                                            modelData[0])
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    x: 6 + 88 + 10
                                    y: 6
                                    height: 24
                                    verticalAlignment: Text.AlignVCenter
                                    text: "通到"
                                    color: Theme.ink3
                                    font.family: Theme.uiFont
                                    font.pixelSize: 11
                                }

                                // 通哪一层：**点开直接打层号**（"2" = 2层 / 通天塔2）。
                                // 用户 2026-10-31 骂掉了"点一下换一层"的循环；一千层的塔
                                // 只能这么选：打 137 回车就到 137 层（没有就建一条空的）。
                                FloorField {
                                    objectName: "floorStairTarget"
                                    x: 6 + 88 + 10 + 34
                                    y: 6
                                    height: 24
                                    width: 90
                                    labelSize: 12
                                    value: String(stairRow.modelData.to || "")
                                    placeholder: "点这里打层号"
                                    showText: function (text) {
                                        return String(stairRow.modelData.to || "") === ""
                                               ? "" : (host.floorShort(text) + " 层")
                                    }
                                    // 点开时填层号（"3"），12 回车 → 还是 3层；
                                    // 用显示文字（"3 层"）当初值会把层名写成 "3 层"
                                    editText: function (text) {
                                        return host.floorShort(text)
                                    }
                                    closeTick: sheetRoot.closeTick
                                    onOpened: function (who) {
                                        sheetRoot.openField = who
                                    }
                                    onClosed: function (who) {
                                        if (sheetRoot.openField === who)
                                            sheetRoot.openField = null
                                    }
                                    onCommitted: function (text) {
                                        host.setStairTargetByName(
                                            sheetRoot.sheetName,
                                            Number(stairRow.modelData.index), text)
                                    }
                                }

                                // ✕ 删这一行楼梯（标错了 / 不需要）：淡着，鼠标在行上才亮
                                Text {
                                    objectName: "floorStairClear"
                                    width: 18
                                    height: 18
                                    anchors.right: parent.right
                                    anchors.rightMargin: 4
                                    y: 9
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    text: "✕"
                                    opacity: stairHover.hovered ? 1.0 : 0.35
                                    color: clearStairMouse.containsMouse
                                           ? Theme.danger : Theme.ink3
                                    font.pixelSize: 11
                                    MouseArea {
                                        id: clearStairMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: host.removeStairRow(
                                            sheetRoot.sheetName,
                                            Number(stairRow.modelData.index))
                                    }
                                }

                                // 第二行：**本层坐标 / 出口坐标**，两个都能点开粘一个坐标进去
                                // （用户 2026-10-30："楼层位置坐标显示两个当前坐标和出口坐标，
                                // 可以通过粘贴修改坐标"；2026-10-31："坐标加层数！！！！！！！！"
                                // —— 左边写本层层号，右边写"→目标层层号"，一眼看出是哪一层的坐标）
                                CoordField {
                                    objectName: "floorStairPos"
                                    x: 6
                                    y: 34
                                    height: 18
                                    width: (parent.width - 12) / 2 - 4
                                    prefix: host.floorShort(sheetRoot.sheetName) + "层 "
                                    placeholder: host.floorShort(sheetRoot.sheetName)
                                                 + "层 没标"
                                    labelSize: 11
                                    row: Number(stairRow.modelData.row)
                                    col: Number(stairRow.modelData.col)
                                    closeTick: sheetRoot.closeTick
                                    onOpened: function (who) {
                                        sheetRoot.openField = who
                                    }
                                    onClosed: function (who) {
                                        if (sheetRoot.openField === who)
                                            sheetRoot.openField = null
                                    }
                                    onCommitted: function (row, col, floorText) {
                                        controller.saveStair(sheetRoot.sheetName,
                                                             Number(stairRow.modelData.index),
                                                             row, col)
                                    }
                                }
                                CoordField {
                                    objectName: "floorStairArrive"
                                    x: 6 + (parent.width - 12) / 2 + 4
                                    y: 34
                                    height: 18
                                    width: (parent.width - 12) / 2 - 4
                                    prefix: String(stairRow.modelData.to || "") === ""
                                            ? "出口 "
                                            : ("→" + host.floorShort(stairRow.modelData.to) + "层 ")
                                    placeholder: String(stairRow.modelData.to || "") === ""
                                                 ? "出口 没标"
                                                 : ("→" + host.floorShort(stairRow.modelData.to)
                                                    + "层 没标")
                                    labelSize: 11
                                    row: Number(stairRow.modelData.toRow)
                                    col: Number(stairRow.modelData.toCol)
                                    closeTick: sheetRoot.closeTick
                                    onOpened: function (who) {
                                        sheetRoot.openField = who
                                    }
                                    onClosed: function (who) {
                                        if (sheetRoot.openField === who)
                                            sheetRoot.openField = null
                                    }
                                    onCommitted: function (row, col, floorText) {
                                        // 粘进来的那截层数就是"通到哪一层"（"→3层 6,7" / "3层 6,7"）；
                                        // 没写层数就只改落点，层不动（用户 2026-10-31：
                                        // "楼梯粘贴出来怎么不带层数？我怎么手动修改？"）
                                        // 序号/层名先拿住：改层会重建这一行，之后再读 modelData 是空
                                        host.setStairArrivalByName(
                                            sheetRoot.sheetName,
                                            Number(stairRow.modelData.index), row, col,
                                            String(floorText || ""))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---- 拉大小：四条边 + 四个角都能拉 ----
        // 用户："怎么只有右下角能拉伸窗口" —— 以前只有一个右下角把手。
        // 一套算法做成 SheetGrip，8 个方位各摆一个。两条要点：
        //   1) 位移必须用**屏幕坐标**（mapToGlobal）：窗口自己在动，
        //      用窗口内坐标算出来的位移会越来越小（实测拖 220px 只挪 110px）；
        //   2) 每帧都把新尺寸记进 floorSizes —— 这扇窗的宽高是绑定出来的，
        //      不记的话绑定会按旧尺寸把窗口顶回去。
        component SheetGrip: Item {
            id: grip
            // 拉哪几条边（两两组合就是角）
            property bool pullLeft: false
            property bool pullRight: false
            property bool pullTop: false
            property bool pullBottom: false
            // 右下角那三道"拉这里"的斜线
            property bool marks: false

            Repeater {
                model: grip.marks ? [4, 9, 14] : []
                delegate: Rectangle {
                    width: 11
                    height: 1
                    color: gripMouse.containsMouse
                           ? Theme.accent : Theme.ink3
                    opacity: 0.6
                    x: grip.width - width - 1
                    y: grip.height - modelData
                    rotation: -45
                    transformOrigin: Item.Right
                }
            }

            MouseArea {
                id: gripMouse
                anchors.fill: parent
                cursorShape: {
                    var horizontal = grip.pullLeft || grip.pullRight
                    var vertical = grip.pullTop || grip.pullBottom
                    if (horizontal && vertical) {
                        // 左上↘右下 / 右上↙左下 两种斜
                        return grip.pullLeft === grip.pullTop
                               ? Qt.SizeFDiagCursor
                               : Qt.SizeBDiagCursor
                    }
                    return horizontal ? Qt.SizeHorCursor
                                      : Qt.SizeVerCursor
                }
                property real pressX: 0
                property real pressY: 0
                property real startX: 0
                property real startY: 0
                property real startW: 0
                property real startH: 0
                onPressed: function (m) {
                    var at = mapToGlobal(m.x, m.y)
                    pressX = at.x
                    pressY = at.y
                    startX = sheetRoot.x
                    startY = sheetRoot.y
                    startW = sheetRoot.width
                    startH = sheetRoot.height
                }
                onPositionChanged: function (m) {
                    if (!pressed)
                        return
                    var at = mapToGlobal(m.x, m.y)
                    var dx = at.x - pressX
                    var dy = at.y - pressY
                    var w = startW + (grip.pullRight ? dx : 0)
                                 - (grip.pullLeft ? dx : 0)
                    var h = startH + (grip.pullBottom ? dy : 0)
                                 - (grip.pullTop ? dy : 0)
                    w = Math.max(sheetRoot.minW, Math.min(sheetRoot.maxW, w))
                    h = Math.max(sheetRoot.minH, Math.min(sheetRoot.maxH, h))
                    // 从上边/左边拉：窗口原点跟着动，另一侧才不动
                    var x = grip.pullLeft
                            ? startX + (startW - w) : startX
                    var y = grip.pullTop
                            ? startY + (startH - h) : startY
                    sheetRoot.x = Math.round(x)
                    sheetRoot.y = Math.round(y)
                    host.saveFloorSize(sheetRoot.sheetName, w, h)
                    // 变大之后可能顶出屏幕：位置一起收回来看得见的地方
                    sheetRoot.clampPos()
                }
                onReleased: {
                    host.saveFloorPos(sheetRoot.sheetName,
                                     sheetRoot.x, sheetRoot.y)
                    host.saveFloorSize(sheetRoot.sheetName,
                                      sheetRoot.width, sheetRoot.height)
                }
            }
        }

        // 四个角
        SheetGrip { objectName: "floorGripTL"
                    pullLeft: true; pullTop: true
                    x: 0; y: 0; width: 10; height: 10 }
        SheetGrip { objectName: "floorGripTR"
                    pullRight: true; pullTop: true
                    x: cardBox.width - 10; y: 0
                    width: 10; height: 10 }
        SheetGrip { objectName: "floorGripBL"
                    pullLeft: true; pullBottom: true
                    x: 0; y: cardBox.height - 12
                    width: 12; height: 12 }
        SheetGrip { objectName: "floorGrip"
                    pullRight: true; pullBottom: true; marks: true
                    x: cardBox.width - 18; y: cardBox.height - 18
                    width: 18; height: 18 }
        // 四条边（角那一段留给角）
        SheetGrip { objectName: "floorGripL"; pullLeft: true
                    x: 0; y: 12; width: 5
                    height: Math.max(1, cardBox.height - 30) }
        SheetGrip { objectName: "floorGripR"; pullRight: true
                    x: cardBox.width - 5; y: 12; width: 5
                    height: Math.max(1, cardBox.height - 30) }
        SheetGrip { objectName: "floorGripT"; pullTop: true
                    x: 10; y: 0; height: 5
                    width: Math.max(1, cardBox.width - 20) }
        SheetGrip { objectName: "floorGripB"; pullBottom: true
                    x: 12; y: cardBox.height - 5; height: 5
                    width: Math.max(1, cardBox.width - 24) }
    }

    // ============ 「⋯」菜单：刷新本层 / 标位置开关 / 删除本层 ============
    // 删除本层要点两下（第一下只上膛，菜单一关就解除）；它不再和主按钮并排。
    Popup {
        id: moreMenu
        objectName: "floorMenu"
        parent: Overlay.overlay
        padding: 4
        width: 168
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onAboutToShow: {
            var at = moreBtn.mapToItem(Overlay.overlay, 0, moreBtn.height + 4)
            moreMenu.x = Math.max(4, Math.min(
                Overlay.overlay.width - moreMenu.width - 4,
                at.x + moreBtn.width - moreMenu.width))
            moreMenu.y = at.y
        }
        onClosed: sheetRoot.deleteArm = false

        background: Rectangle {
            radius: 8
            color: Theme.paper
            border.width: 1
            border.color: Theme.cardEdge
        }

        contentItem: Column {
            spacing: 0

            component MenuRow: Rectangle {
                id: menuRow
                property string label: ""
                property bool danger: false
                signal triggered()
                width: parent ? parent.width : 160
                height: 30
                radius: 6
                color: menuMouse.containsMouse
                       ? (menuRow.danger ? Theme.dangerSoft : Theme.hover)
                       : "transparent"
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: menuRow.label
                    color: menuRow.danger ? Theme.danger : Theme.ink
                    font.family: Theme.uiFont
                    font.pixelSize: 12
                }
                MouseArea {
                    id: menuMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: menuRow.triggered()
                }
            }

            MenuRow {
                objectName: "floorRefresh"
                label: "刷新本层"
                onTriggered: {
                    controller.refreshFloorCounts(sheetRoot.sheetName)
                    moreMenu.close()
                }
            }
            MenuRow {
                objectName: "floorGridToggle"
                label: sheetRoot.gridEditActive ? "退出标位置" : "进入标位置"
                onTriggered: {
                    host.gridEditToggle(sheetRoot.sheetName)
                    moreMenu.close()
                }
            }
            Rectangle {
                width: parent.width
                height: 1
                color: Theme.hairline
            }
            MenuRow {
                objectName: "floorDelete"
                danger: true
                label: sheetRoot.deleteArm ? "再点一次：确认删除" : "删除本层"
                onTriggered: {
                    if (!sheetRoot.deleteArm) {
                        sheetRoot.deleteArm = true
                        return
                    }
                    moreMenu.close()
                    controller.removeFloor(sheetRoot.sheetName)
                    host.closeFloorSheet(sheetRoot.sheetName)
                }
            }
        }
    }

    // ============ 加怪 / 加资源：从按钮下面弹出的下拉菜单 ============
    // 用户："地图下的加怪和加资源怎么不是下拉菜单" —— 以前是整个窗口铺一层
    // 挑选页，把地图小窗和地图都盖住了；现在跟"加技能"一样，挂在按钮下面。
    // 小窗是独立窗口了，菜单就画在**这一扇窗**里（按它的高度收着放，不会被裁）。
    // 宿主写 `sheetRoot.host`：写 `host: host` 会自引用成 undefined。
    PickMenu { host: sheetRoot.host; sheetName: sheetRoot.sheetName }
}
