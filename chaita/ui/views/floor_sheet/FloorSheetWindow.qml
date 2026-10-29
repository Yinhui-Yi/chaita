import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
// 配色/按钮在上一层（docs/UI_MAP.md）
import ".."
import "../shared"
// 它自己的下拉菜单（一个界面一个文件夹）
import "pick_menu"
import "route_layer"
// 格子编辑：编辑模式下的坐标系 + 悬停/长按抓格
import "grid_layer"

// 「这一层」小窗：这一层有什么怪、哪些资源、各几个；就地改数量、点图标换种类、
// 刷新本层 / 删除本层 / 写备忘。
//
// 它是**一扇真窗口**（无边框 + 置顶 + Qt.Tool）：能拖到桌面任何地方、能多开
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
    // 删本层的两步确认是"每扇窗各自"的
    property bool deleteArm: false
    property string sheetName: ""
    // 格子编辑模式：只有这一层在编辑时才开（主窗口的 gridEditOn/Floor 是全局一份）
    readonly property bool gridEditActive:
        host.gridEditOn && host.gridEditFloor === sheetRoot.sheetName

    // 编辑模式：这个词条出现在哪些格（1 开始的行列，和"第几行第几列"一致）
    // 资源按"名字+效果"认：两个同名血瓶各标各的，互不串
    function gridPosText(name, effect) {
        if (!sheetRoot.gridEditActive)
            return ""
        var pos = host.gridPositionsFor(sheetRoot.sheetName, String(name || ""),
                                        String(effect || ""))
        if (pos.length === 0)
            return "没标位置"
        var parts = []
        for (var i = 0; i < pos.length; i++)
            parts.push((Number(pos[i].row) + 1) + "," + (Number(pos[i].col) + 1))
        return "位置 " + parts.join(" · ")
    }
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
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
    readonly property int maxW: Math.max(230, screenRect.width - 16)
    readonly property int maxH: Math.max(180, screenRect.height - 56)
    // 列表里缩略图的边长：怪物行、资源行**同一条规矩**，别再一个 20 一个 24
    // （用户："地图下资源界面素材的缩略图太大了"）
    readonly property int thumbSide: 20
    // 数量框的宽（含右边那两个箭头）：一个数字 + 两个箭头，别留一大截空白
    readonly property int countBoxW: 34
    // 窗口大小跟着卡片走：拉过大就按拉的，没拉过按内容撑
    width: Math.round(cardBox.sized
                      ? Math.max(230, Math.min(maxW, cardBox.wantedW))
                      : 300)
    height: Math.round(cardBox.sized
                       ? Math.max(180, Math.min(maxH, cardBox.wantedH))
                       : Math.min(maxH,
                                  26 + sheetShotBox.height + 6
                                  + Math.min(sheetBody.implicitHeight,
                                             cardBox.listMax)
                                  + 34))
    // 整块钳在屏幕里：拖到屏幕边上就停住，但**不能**把越界的那截攒着 ——
    // 攒着的话往回拖要先"还债"，窗口会卡住/跳（用户："一直在抖动"）。
    // 边也要钳：不然拉大以后右下角的拉大手柄会跑到屏幕外点不到。
    function clampPos() {
        var rect = sheetRoot.screenRect
        if (!rect)
            return
        var left = rect.x + 2
        var top = rect.y + 2
        var right = Math.max(left, rect.x + rect.width - sheetRoot.width - 2)
        var bottom = Math.max(top, rect.y + rect.height - sheetRoot.height - 2)
        sheetRoot.x = Math.round(Math.max(left, Math.min(sheetRoot.x, right)))
        sheetRoot.y = Math.round(Math.max(top, Math.min(sheetRoot.y, bottom)))
    }
    // 按 Esc 关这一扇（焦点在哪个窗口上，事件就到哪个窗口）
    Shortcut {
        sequence: "Esc"
        onActivated: host.closeFloorSheet(sheetRoot.sheetName)
    }
    // 点了别处（比如主窗口）：正在开的下拉菜单收起来
    onActiveChanged: {
        if (!sheetRoot.active && host.pickMode !== ""
            && String(host.pickFloor) === sheetRoot.sheetName)
            host.pickMode = ""
    }

    Rectangle {
        id: cardBox
        objectName: "floorCard"
        anchors.fill: parent
        // 用户拉过大小没有（拉过就按拉的来，没拉过就按内容撑）
        readonly property bool sized:
            host.floorSizes[sheetRoot.sheetName] !== undefined
        readonly property real wantedW: Math.max(230, Math.min(
            sheetRoot.maxW, host.floorW(sheetRoot.sheetName, 300)))
        readonly property real wantedH: Math.max(180, Math.min(
            sheetRoot.maxH, host.floorH(sheetRoot.sheetName, 180)))
        // 固定件：抬头 26 + 截图 + 间距 6 + 底部 34
        readonly property int fixedH: 26 + sheetShotBox.height + 6 + 34
        // 列表能占多高：拉过大小就吃掉剩下的，没拉过最多 150
        readonly property int listMax: sized
            ? Math.max(40, Math.round(wantedH) - fixedH)
            : Math.max(60, Math.min(150, Math.round(sheetRoot.maxH)
                                    - 16 - fixedH))
        radius: 8
        color: host.paperHi
        border.width: 1
        border.color: host.edge
        clip: true
        MouseArea { anchors.fill: parent }

        // 抬头：可以拖着走
        Item {
            x: 6
            y: 2
            width: cardBox.width - 12
            height: 22

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
                anchors.verticalCenter: parent.verticalCenter
                // 用户："标题里的怪物数量资源数量，剩xxx都删了，毫无意义"
                width: parent.width - 56
                text: sheetRoot.sheetName
                color: host.ink
                font.family: host.uiFont
                font.pixelSize: 13
                font.bold: true
                elide: Text.ElideRight
            }
            // 再开一层：把这层后面还没开的那层打开
            // （窗口挡住地图块时，这是多开最直接的路）
            Item {
                id: sheetMore
                objectName: "floorMore"
                anchors.right: sheetClose.left
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 16
                height: 16
                Text {
                    anchors.centerIn: parent
                    text: "＋"
                    color: sheetMoreMouse.containsMouse
                           ? host.amber : host.ink3
                    font.pixelSize: 12
                    font.bold: true
                }
                MouseArea {
                    id: sheetMoreMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.openNextFloor(sheetRoot.sheetName)
                }
            }

            Item {
                id: sheetClose
                objectName: "floorClose"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 16
                height: 16
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: sheetCloseMouse.containsMouse
                           ? host.danger : host.ink3
                    font.pixelSize: 11
                }
                MouseArea {
                    id: sheetCloseMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.closeFloorSheet(sheetRoot.sheetName)
                }
            }
        }

        // 截图：整张（只缩不放），点开看大图
        Rectangle {
            id: sheetShotBox
            objectName: "floorShotBox"
            x: 6
            y: 26
            width: cardBox.width - 12
            // 截图区跟着卡片一起变大（用户："放大地图的小窗的时候
            // 地图不会一起变大"）：
            //   · 宽度撑满卡片，高度按截图比例算（宽图不再只占中间一小条）；
            //   · 用户把卡片拉大了，就把"给清单留 60 之外"的高度都给它；
            //   · 没拉过就按比例撑高，最多 240（别让默认卡片一开就顶满屏）。
            readonly property real shotW: cardBox.width - 12
            readonly property real ratio:
                (shotImage.sourceSize.width > 0
                 && shotImage.sourceSize.height > 0)
                ? shotImage.sourceSize.width / shotImage.sourceSize.height
                : (16 / 9)
            readonly property real aspectH: shotW / ratio
            readonly property real maxH: cardBox.sized
                ? Math.max(64, cardBox.wantedH - 26 - 6 - 34 - 60)
                : Math.max(64, Math.min(
                       240, host.height - 8 - 26 - 6 - 34 - 60))
            height: Math.max(64, Math.min(aspectH, maxH))
            radius: 8
            color: host.paperLo
            border.width: 1
            border.color: host.hairline
            clip: true

            // 图实际画出来的那一块：PreserveAspectFit 会按比例缩、居中，
            // 路线层必须贴着**这一块**（贴外框的话红线和格子对不上，用户："格子会偏"）
            readonly property real innerW: width - 8
            readonly property real innerH: height - 8
            readonly property real drawnW: Math.min(innerW, innerH * ratio)
            readonly property real drawnH: drawnW / ratio

            Image {
                id: shotImage
                objectName: "floorShot"
                anchors.fill: parent
                anchors.margins: 4
                source: host.sheetShot(sheetRoot.sheetName)
                visible: host.hasUrl(host.sheetShot(sheetRoot.sheetName))
                fillMode: Image.PreserveAspectFit
                smooth: false
                asynchronous: true
            }
            // 路线提取：长按玩家起步、拖过相邻格画红线（见 docs/ROUTE.md）。
            // 一格多大由 AI 读到的行列换算（`host.routeCell`），铺在图上那块矩形里。
            Item {
                id: shotDrawn
                x: 4 + (sheetShotBox.innerW - sheetShotBox.drawnW) / 2
                y: 4 + (sheetShotBox.innerH - sheetShotBox.drawnH) / 2
                width: Math.max(1, sheetShotBox.drawnW)
                height: Math.max(1, sheetShotBox.drawnH)

                RouteLayer {
                    id: routeLayer
                    objectName: "routeLayer"
                    anchors.fill: parent
                    floorName: sheetRoot.sheetName
                    cell: host.routeCell(sheetRoot.sheetName, width)
                    onFinished: function (cells) {
                        host.storeRoute(sheetRoot.sheetName, cells)
                        routeLayer.clear()
                    }
                }
                // 格子编辑：编辑模式下盖在路线层上面，画坐标系 + 悬停/长按抓格
                GridLayer {
                    id: gridLayer
                    objectName: "gridLayer"
                    anchors.fill: parent
                    host: sheetRoot.host
                    floorName: sheetRoot.sheetName
                    cell: host.routeCell(sheetRoot.sheetName, width)
                    side: host.routeCols
                    editing: sheetRoot.gridEditActive
                    gridCells: {
                        if (!controller)
                            return []
                        controller.mapHistory   // 绑一下：assign 后会重取
                        return controller.gridCells(sheetRoot.sheetName)
                    }
                    onDragStart: function (row, col) {
                        // 有 Ctrl 多选的格子就一起搬过去，否则只搬按住的这一格。
                        var multi = host.gridMulti || []
                        var payload = multi.length > 0
                                ? { "cells": multi }
                                : { "row": row, "col": col }
                        gridDragChip.Drag.mimeData = {
                            "application/x-grid-cell": JSON.stringify(payload) }
                        gridDragChip.visible = true
                        gridDragChip.Drag.active = true
                    }
                    onCellCleared: function (row, col) {
                        host.gridAssign(row, col, "", "")
                    }
                }
            }
            Text {
                anchors.centerIn: parent
                visible: !host.hasUrl(host.sheetShot(sheetRoot.sheetName))
                text: "这一层还没有截图"
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 10
            }
            // 格子编辑开关：压在截图右上角（编辑中 = 实心「完成」）
            FlatBtn {
                id: gridEditBtn
                objectName: "floorGridEdit"
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.top: parent.top
                anchors.topMargin: 6
                solid: sheetRoot.gridEditActive
                label: sheetRoot.gridEditActive ? "完成" : "编辑"
                onClicked: host.gridEditToggle(sheetRoot.sheetName)
            }
        }

        // 清单：怪 / 资源 / 备忘
        Flickable {
            id: sheetFlick
            objectName: "floorFlick"
            x: 6
            y: sheetShotBox.y + sheetShotBox.height + 6
            width: cardBox.width - 12
            height: Math.min(sheetBody.implicitHeight, cardBox.listMax)
            contentWidth: width
            contentHeight: sheetBody.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: sheetBody
                width: sheetFlick.width
                spacing: 0

                // ---------- 怪 ----------
                Item {
                    width: sheetBody.width
                    height: 22
                    Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "怪物"
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 10
                        font.letterSpacing: 2
                    }
                    FlatBtn {
                        id: addMonBtn
                        objectName: "floorAddMon"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        label: "＋ 加怪"
                        onClicked: host.openPickMenu(
                            "mon", sheetRoot.sheetName, addMonBtn,
                            -1, sheetRoot)
                    }
                }

                Repeater {
                    model: host.sheetMons(sheetRoot.sheetName)
                    delegate: Item {
                        id: monRow
                        objectName: "floorMonRow"
                        width: sheetBody.width
                        // 用户："怪物和资源的行间距太大了" —— 30 → 24。
                        // 一行 24 = 20 的缩略图 + 上下各 2，密但不挤；编辑模式加一行位置
                        height: 24 + (sheetRoot.gridEditActive ? 14 : 0)

                        readonly property var mon: modelData || ({})
                        readonly property string monIcon: host.hasUrl(mon.icon)
                            ? String(mon.icon)
                            : host.monsterIconNamed(mon.name)

                        // 拖拽落点高亮（编辑模式：把坐标拖到这个词条上）
                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: Qt.rgba(0.84, 0.62, 0.18, 0.16)
                            visible: monDrop.containsDrag
                        }

                        Column {
                            anchors.fill: parent
                            Row {
                                width: parent.width
                                height: 24
                                spacing: 5

                                Text {
                                    objectName: "floorMonDone"
                                    width: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignHCenter
                                    text: monRow.mon.done ? "●" : "○"
                                    color: monRow.mon.done ? host.amber : host.ink3
                                    font.pixelSize: 11
                                    MouseArea {
                                        anchors.fill: parent
                                        anchors.margins: -4
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: controller.toggleFloorMonsterDone(
                                            sheetRoot.sheetName, index)
                                    }
                                }

                                Rectangle {
                                    objectName: "floorMonThumb"
                                    width: sheetRoot.thumbSide
                                    height: sheetRoot.thumbSide
                                    radius: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: host.paperLo
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
                                        color: host.ink3
                                        font.family: host.uiFont
                                        font.pixelSize: 9
                                    }
                                }

                                Rectangle {
                                    width: parent.width - 14 - 20 - 34 - 16 - 4 * 5 - 2
                                    height: 22
                                    radius: 5
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: nameField.activeFocus
                                           ? host.paperLo : "transparent"
                                    TextField {
                                        id: nameField
                                        objectName: "floorMonName"
                                        anchors.fill: parent
                                        anchors.leftMargin: 4
                                        anchors.rightMargin: 4
                                        verticalAlignment: TextInput.AlignVCenter
                                        background: null
                                        color: host.ink
                                        font.family: host.uiFont
                                        font.pixelSize: 10
                                        selectByMouse: true
                                        text: monRow.mon.name || ""
                                        onEditingFinished: controller.saveFloorMonsterField(
                                            sheetRoot.sheetName, index, "name", text)
                                    }
                                }
                                Rectangle {
                                    width: 34
                                    height: 22
                                    radius: 5
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: countField.activeFocus
                                           ? host.paperLo : "transparent"
                                    TextField {
                                        id: countField
                                        objectName: "floorMonCount"
                                        anchors.fill: parent
                                        horizontalAlignment: TextInput.AlignHCenter
                                        verticalAlignment: TextInput.AlignVCenter
                                        background: null
                                        color: host.ink2
                                        font.family: host.monoFont
                                        font.pixelSize: 10
                                        selectByMouse: true
                                        text: monRow.mon.count === undefined
                                              ? "" : String(monRow.mon.count)
                                        onEditingFinished: controller.saveFloorMonsterField(
                                            sheetRoot.sheetName, index, "count", text)
                                    }
                                }
                                Text {
                                    objectName: "floorMonDelete"
                                    width: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignHCenter
                                    text: "✕"
                                    color: deleteMonMouse.containsMouse
                                        ? host.danger : host.ink3
                                    font.pixelSize: 10
                                    MouseArea {
                                        id: deleteMonMouse
                                        anchors.fill: parent
                                        anchors.margins: -4
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: controller.removeFloorMonster(
                                            sheetRoot.sheetName, index)
                                    }
                                }
                            }
                            // 编辑模式：这个词条出现在哪些格（1 开始的行列）。
                            // 点它 = 选中/取消选中这个词条（选中的格子在图上才是黄的）
                            Text {
                                objectName: "floorMonPos"
                                width: parent.width
                                height: 14
                                visible: sheetRoot.gridEditActive
                                leftPadding: 14
                                verticalAlignment: Text.AlignVCenter
                                text: {
                                    controller.mapHistory   // 绑一下：格子改了要重取
                                    return sheetRoot.gridPosText(monRow.mon.name)
                                }
                                color: String(host.gridSelected || "") === monRow.mon.name
                                       ? host.amber : host.ink3
                                font.family: host.uiFont
                                font.pixelSize: 8
                                elide: Text.ElideRight
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: host.gridSelect(monRow.mon.name)
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

                Item {
                    width: sheetBody.width
                    height: 10
                }

                // ---------- 资源 ----------
                Item {
                    width: sheetBody.width
                    height: 22
                    Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "资源"
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 10
                        font.letterSpacing: 2
                    }
                    FlatBtn {
                        id: addItemBtn
                        objectName: "floorAddItem"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        label: "＋ 加资源"
                        onClicked: host.openPickMenu(
                            "item", sheetRoot.sheetName, addItemBtn,
                            -1, sheetRoot)
                    }
                }

                Repeater {
                    // 资源按习惯顺序显示（用户："资源怎么不按习惯排序"）：
                    // 顺序由 Python 算，绑一下 mapHistory 让它改了会重排
                    model: {
                        if (!controller)
                            return []
                        controller.mapHistory   // 绑一下：改了会重排
                        return controller.sortedSheetItems(
                                   sheetRoot.sheetName)
                    }
                    delegate: Item {
                        id: itemRow
                        objectName: "floorItemRow"
                        width: sheetBody.width
                        // 和怪物行同一个高度；多段效果那行（黄宝石）要换行，就跟着长
                        // （用户："行间距太大了" —— 单段效果的还是 24）；编辑模式加一行位置
                        height: Math.max(24, effectCell.height + 4)
                                + (sheetRoot.gridEditActive ? 14 : 0)

                        readonly property var item: modelData || ({})
                        readonly property string itemName: String(item.name || "")

                        // 拖拽落点高亮（编辑模式：把坐标拖到这个词条上）
                        Rectangle {
                            anchors.fill: parent
                            radius: 4
                            color: Qt.rgba(0.84, 0.62, 0.18, 0.16)
                            visible: itemDrop.containsDrag
                        }

                        Column {
                            anchors.fill: parent
                            Row {
                                width: parent.width
                                height: Math.max(24, effectCell.height + 4)
                                spacing: 5

                                Text {
                                    objectName: "floorItemDone"
                                    width: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignHCenter
                                    text: itemRow.item.done ? "●" : "○"
                                    color: itemRow.item.done ? host.amber : host.ink3
                                    font.pixelSize: 11
                                    MouseArea {
                                        anchors.fill: parent
                                        anchors.margins: -4
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: controller.toggleFloorItemDone(
                                            sheetRoot.sheetName, itemRow.item._src)
                                    }
                                }
                                // 缩略图**代替名字**（用户："不要写什么 X宝石 / X钥匙，
                                // 用缩略图代替"），所以它占的是原来名字那一格。
                                // 边长跟怪物行同一条规矩（sheetRoot.thumbSide）
                                Image {
                                    id: floorItemIcon
                                    objectName: "floorItemIcon"
                                    width: sheetRoot.thumbSide
                                    height: sheetRoot.thumbSide
                                    anchors.verticalCenter: parent.verticalCenter
                                    source: host.itemIcon(itemRow.item.icon || "")
                                    visible: status === Image.Ready
                                    fillMode: Image.PreserveAspectFit
                                    smooth: false
                                    // 点图标换种类（用户："资源只有数值和数量能改"）
                                    MouseArea {
                                        objectName: "floorItemIconPick"
                                        anchors.fill: parent
                                        anchors.margins: -4
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: host.openPickMenu(
                                            "item", sheetRoot.sheetName,
                                            addItemBtn, itemRow.item._src,
                                            sheetRoot)
                                    }
                                }
                                // 没图（名字对不上道具表 / 临时图被清了）就画个空框 + 首字，
                                // 别让这一行的图位置空着（用户："资源的缩略图怎么不全"）
                                Rectangle {
                                    objectName: "floorItemIconFallback"
                                    width: sheetRoot.thumbSide
                                    height: sheetRoot.thumbSide
                                    radius: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: host.paperLo
                                    visible: floorItemIcon.status !== Image.Ready
                                    Text {
                                        anchors.centerIn: parent
                                        text: itemRow.itemName
                                              ? itemRow.itemName.charAt(0) : "?"
                                        color: host.ink3
                                        font.family: host.uiFont
                                        font.pixelSize: 10
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: host.openPickMenu(
                                            "item", sheetRoot.sheetName,
                                            addItemBtn, itemRow.item._src,
                                            sheetRoot)
                                    }
                                }
                                // 效果：一段一条「属性 + 加减号 + 数字框」，属性写死、数值能改
                                // （用户："宝石加的属性要写死，加的数值要能改"、
                                //  "黄宝石每个值都要能改"）。控件是 shared/EffectEditor.qml，
                                // 伤害计算那张卡用的是同一个，别各画一套。
                                Item {
                                    id: effectCell
                                    readonly property var partList: controller
                                        ? controller.itemEffectPartList(itemRow.item.effect || "")
                                        : []
                                    width: parent.width - 14 - sheetRoot.thumbSide
                                           - sheetRoot.countBoxW - 16 - 4 * 5
                                    height: Math.max(20, effectEditor.implicitHeight)
                                    anchors.verticalCenter: parent.verticalCenter

                                    EffectEditor {
                                        id: effectEditor
                                        width: parent.width
                                        fieldName: "floorItemEffect"
                                        parts: effectCell.partList
                                        onPartChanged: function (partIndex, value) {
                                            controller.saveItemEffectPartValue(
                                                sheetRoot.sheetName, itemRow.item._src,
                                                partIndex, value)
                                        }
                                    }
                                }
                                // 数量：同一个数字框（也能直接打字）
                                NumberStepper {
                                    objectName: "floorItemCountBox"
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
                                Text {
                                    objectName: "floorItemDelete"
                                    width: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignHCenter
                                    text: "✕"
                                    color: deleteItemMouse.containsMouse
                                        ? host.danger : host.ink3
                                    font.pixelSize: 10
                                    MouseArea {
                                        id: deleteItemMouse
                                        anchors.fill: parent
                                        anchors.margins: -4
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: controller.removeItem(
                                            sheetRoot.sheetName,
                                            itemRow.item._src)
                                    }
                                }
                            }
                            // 编辑模式：这个词条出现在哪些格（1 开始的行列）
                            Text {
                                objectName: "floorItemPos"
                                width: parent.width
                                height: 14
                                visible: sheetRoot.gridEditActive
                                leftPadding: 14
                                verticalAlignment: Text.AlignVCenter
                                text: {
                                    controller.mapHistory   // 绑一下：格子改了要重取
                                    return sheetRoot.gridPosText(itemRow.itemName,
                                                                 itemRow.item.effect)
                                }
                                color: String(host.gridSelected || "") === itemRow.itemName
                                       ? host.amber : host.ink3
                                font.family: host.uiFont
                                font.pixelSize: 8
                                elide: Text.ElideRight
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: host.gridSelect(itemRow.itemName)
                                }
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

                Item {
                    width: sheetBody.width
                    height: 14
                }

                // ---------- 提取出来的路线 ----------
                // 长按玩家拖出来的那些（docs/ROUTE.md）：这一层的路线列在这儿。
                // 点「路线 N」把那条"交互路线"（勇者 → 格1,1 → …）摆出来；
                // 右边是**备注**（用户："把路线的 xx格 删掉改成备注，备注默认是玩家路线
                // 最后的血量攻击防御魔防，玩家可以添加其他信息"）。
                Repeater {
                    model: host.floorRoutes(sheetRoot.sheetName)
                    delegate: Row {
                        objectName: "routeRow"
                        width: sheetBody.width
                        height: 22
                        spacing: 4
                        Text {
                            id: routeName
                            objectName: "routeOpen"
                            width: 52
                            anchors.verticalCenter: parent.verticalCenter
                            text: "路线 " + (index + 1)
                            color: routeMouse.containsMouse ? host.amber : host.ink2
                            font.family: host.uiFont
                            font.pixelSize: 9
                            MouseArea {
                                id: routeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: host.openRoute(sheetRoot.sheetName,
                                                          modelData.index)
                            }
                        }
                        // 计算部分（只读）：走完这条路之后的血/攻/防/魔防，
                        // 按当前格子实时算（用户："计算部分不再允许修改"）
                        Text {
                            objectName: "routeComputed"
                            width: 116
                            anchors.verticalCenter: parent.verticalCenter
                            text: host.routeStatsFor(sheetRoot.sheetName,
                                                     modelData.index)
                            color: host.ink3
                            font.family: host.monoFont
                            font.pixelSize: 8
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            width: parent.width - 52 - 116 - 12 - 16
                            height: 22
                            radius: 5
                            anchors.verticalCenter: parent.verticalCenter
                            color: memoField.activeFocus
                                   ? host.paperLo : "transparent"
                            border.width: 1
                            border.color: memoField.activeFocus
                                          ? host.amber : host.hairline
                            TextField {
                                id: memoField
                                objectName: "routeMemo"
                                anchors.fill: parent
                                anchors.leftMargin: 4
                                anchors.rightMargin: 4
                                verticalAlignment: TextInput.AlignVCenter
                                background: null
                                color: host.ink
                                font.family: host.uiFont
                                font.pixelSize: 9
                                selectByMouse: true
                                text: modelData.memo || ""
                                onEditingFinished: controller.saveRouteMemo(
                                    sheetRoot.sheetName, modelData.index, text)
                            }
                        }
                        Text {
                            objectName: "routeRowDelete"
                            width: 16
                            anchors.verticalCenter: parent.verticalCenter
                            horizontalAlignment: Text.AlignHCenter
                            text: "✕"
                            color: deleteRouteMouse.containsMouse
                                    ? host.danger : host.ink3
                            font.pixelSize: 10
                            MouseArea {
                                id: deleteRouteMouse
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: controller.removeRoute(
                                    sheetRoot.sheetName, modelData.index)
                            }
                        }
                    }
                }

                // ---------- 备忘 ----------
                Item {
                    width: sheetBody.width
                    height: 24
                    Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: 30
                        text: "备忘"
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 9
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.leftMargin: 32
                        anchors.right: parent.right
                        height: 22
                        radius: 5
                        anchors.verticalCenter: parent.verticalCenter
                        color: memoField.activeFocus
                               ? host.paperLo : "transparent"
                        border.width: 1
                        border.color: memoField.activeFocus
                                      ? host.amber : host.hairline
                        TextField {
                            id: memoField
                            objectName: "floorMemo"
                            anchors.fill: parent
                            anchors.leftMargin: 5
                            anchors.rightMargin: 5
                            verticalAlignment: TextInput.AlignVCenter
                            background: null
                            color: host.ink
                            font.family: host.uiFont
                            font.pixelSize: 10
                            selectByMouse: true
                            // 每扇窗自己带出这一层的备忘
                            text: host.sheetMemo(sheetRoot.sheetName)
                            onEditingFinished: controller.saveFloorMemo(
                                sheetRoot.sheetName, text)
                        }
                    }
                }

                Item {
                    width: sheetBody.width
                    height: 6
                }
            }
        }

        // 底部：刷新本层 / 删除本层 / 完成（右下角 20px 留给拉大的手柄）
        Row {
            x: 6
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 6
            width: cardBox.width - 12 - 20
            spacing: 6

            FlatBtn {
                objectName: "floorRefresh"
                label: "刷新本层"
                onClicked: controller.refreshFloorCounts(
                    sheetRoot.sheetName)
            }
            FlatBtn {
                objectName: "floorDelete"
                danger: true
                label: sheetRoot.deleteArm ? "再点一次删除" : "删除本层"
                onClicked: {
                    if (!sheetRoot.deleteArm) {
                        sheetRoot.deleteArm = true
                        return
                    }
                    controller.removeFloor(sheetRoot.sheetName)
                    host.closeFloorSheet(sheetRoot.sheetName)
                }
            }
            Item {
                width: Math.max(0, parent.width - 2 * 74 - 46 - 12)
                height: 1
            }
            FlatBtn {
                objectName: "floorDone"
                solid: true
                label: "完成"
                onClicked: {
                    controller.markFloorSaved(sheetRoot.sheetName)
                    host.closeFloorSheet(sheetRoot.sheetName)
                }
            }
        }

        // ---- 拖拽时跟着光标的小牌子：长按抓格后浮起来，拖到词条上松手 ----
        Item {
            id: gridDragChip
            visible: false
            z: 40
            width: 64
            height: 22
            Drag.dragType: Drag.Automatic
            Drag.hotSpot: Qt.point(10, 11)
            Drag.mimeData: { "application/x-grid-cell": "" }
            Drag.onDragFinished: {
                gridDragChip.visible = false
                host.gridDrag = ({})
                host.gridHover = ({})
            }
            Rectangle {
                anchors.fill: parent
                radius: 4
                color: Theme.amber
                Text {
                    anchors.centerIn: parent
                    text: (host.gridMulti || []).length > 1
                          ? (host.gridMulti.length + " 格")
                          : (host.gridDrag.row !== undefined
                             ? "格 " + (Number(host.gridDrag.row) + 1) + ","
                               + (Number(host.gridDrag.col) + 1)
                             : "")
                    color: Theme.paperHi
                    font.family: Theme.uiFont
                    font.pixelSize: 9
                    font.bold: true
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
                           ? host.amber : host.ink3
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
                    w = Math.max(230, Math.min(sheetRoot.maxW, w))
                    h = Math.max(180, Math.min(sheetRoot.maxH, h))
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

    // ============ 加怪 / 加资源：从按钮下面弹出的下拉菜单 ============
    // 用户："地图下的加怪和加资源怎么不是下拉菜单" —— 以前是整个窗口铺一层
    // 挑选页，把地图小窗和地图都盖住了；现在跟"加技能"一样，挂在按钮下面。
    // 小窗是独立窗口了，菜单就画在**这一扇窗**里（按它的高度收着放，不会被裁）。
    // 宿主写 `sheetRoot.host`：写 `host: host` 会自引用成 undefined。
    PickMenu { host: sheetRoot.host; sheetName: sheetRoot.sheetName }
}
