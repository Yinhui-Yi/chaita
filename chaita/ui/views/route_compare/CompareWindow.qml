import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 配色/按钮在上一层：views/shared
import "../shared"

// 路线对比（独立窗口：无边框 + 置顶 + Qt.Tool，能摆在游戏旁边）。
//
// 用户："实现一个路线对比功能，入口就在伤害计算的右边；将一条算好的路线通过
// 复制或拖动导入后，显示每个怪物的掉血；有多条路线时对比每个怪在不同路线的掉血"。
//
// 状态在**主窗口**的 `compare*` 上（`host.compareRoutes` 等），这一份只画和点：
// 一条路线一列，一行一只怪（按「名字 + 第几只」对齐），底下是每条路线的合计。
Window {
    id: compareWin
    // 主窗口（状态都在它身上）
    property var host

    objectName: "compareWindow"
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    readonly property var screenRect: {
        var scr = compareWin.screen
        if (!scr)
            return Qt.rect(0, 0, 1920, 1080)
        var originX = scr.virtualX !== undefined ? scr.virtualX : 0
        var originY = scr.virtualY !== undefined ? scr.virtualY : 0
        return Qt.rect(originX, originY, scr.width, scr.height)
    }
    readonly property int maxH: Math.max(220, screenRect.height - 72)
    // 列宽：怪物名 92、每条路线 66
    readonly property int nameW: 92
    readonly property int routeW: 72
    readonly property int autoW: nameW + (host.compareRoutes || []).length * routeW + 26
    readonly property int autoH: 30 + 22
        + Math.max(24, Math.min(320, compareCol.implicitHeight)) + 34

    width: Math.max(300, host.compareWinW > 0 ? host.compareWinW : autoW)
    height: Math.max(110, host.compareWinH > 0
                     ? host.compareWinH : Math.min(maxH, autoH))

    function clampPos() {
        var rect = compareWin.screenRect
        if (!rect)
            return
        var left = rect.x + 2
        var top = rect.y + 2
        var right = Math.max(left, rect.x + rect.width - compareWin.width - 2)
        var bottom = Math.max(top, rect.y + rect.height - compareWin.height - 2)
        compareWin.x = Math.round(Math.max(left, Math.min(compareWin.x, right)))
        compareWin.y = Math.round(Math.max(top, Math.min(compareWin.y, bottom)))
    }

    // 开窗时摆在主窗口右边；伤害计算开着就摆它右边，别两个叠一起
    function place() {
        var rect = compareWin.screenRect
        if (!rect)
            return
        var baseX = host.x + host.width + 8
        if (host.battleWindow && host.battleWindow.visible)
            baseX = host.battleWindow.x + host.battleWindow.width + 8
        compareWin.x = Math.round(Math.max(
            rect.x + 4,
            Math.min(baseX,
                     rect.x + rect.width - compareWin.width - 12)))
        compareWin.y = Math.round(Math.max(
            rect.y + 4,
            Math.min(host.y + 60,
                     rect.y + rect.height - compareWin.height - 12)))
    }

    Shortcut {
        sequence: "Esc"
        onActivated: host.closeCompare()
    }

    // ---- 拉大小：四条边 + 四个角（和伤害计算同一套算法）----
    component CompareGrip: Item {
        id: grip
        property bool pullLeft: false
        property bool pullRight: false
        property bool pullTop: false
        property bool pullBottom: false

        MouseArea {
            anchors.fill: parent
            cursorShape: {
                var horizontal = grip.pullLeft || grip.pullRight
                var vertical = grip.pullTop || grip.pullBottom
                if (horizontal && vertical)
                    return grip.pullLeft === grip.pullTop
                           ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
                return horizontal ? Qt.SizeHorCursor : Qt.SizeVerCursor
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
                startX = compareWin.x
                startY = compareWin.y
                startW = compareWin.width
                startH = compareWin.height
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
                w = Math.max(300, Math.min(compareWin.screenRect.width - 8, w))
                h = Math.max(110, Math.min(compareWin.maxH, h))
                var x = grip.pullLeft ? startX + (startW - w) : startX
                var y = grip.pullTop ? startY + (startH - h) : startY
                host.compareWinW = Math.round(w)
                host.compareWinH = Math.round(h)
                compareWin.x = Math.round(x)
                compareWin.y = Math.round(y)
                compareWin.clampPos()
            }
        }
    }

    Rectangle {
        id: compareCard
        objectName: "compareCard"
        anchors.fill: parent
        radius: 8
        color: Theme.paperHi
        border.width: 1
        border.color: Theme.edge
        clip: true
        MouseArea { anchors.fill: parent }

        // ---- 抬头：拖着走 + 粘贴 + 清空 + 关 ----
        Item {
            id: compareHeader
            x: 6
            y: 2
            width: parent.width - 12
            height: 28
            MouseArea {
                objectName: "compareDrag"
                anchors.fill: parent
                property real pressX: 0
                property real pressY: 0
                property real startX: 0
                property real startY: 0
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.ArrowCursor
                onPressed: function (m) {
                    var at = mapToGlobal(m.x, m.y)
                    pressX = at.x
                    pressY = at.y
                    startX = compareWin.x
                    startY = compareWin.y
                }
                onPositionChanged: function (m) {
                    if (!pressed)
                        return
                    var at = mapToGlobal(m.x, m.y)
                    compareWin.x = Math.round(startX + (at.x - pressX))
                    compareWin.y = Math.round(startY + (at.y - pressY))
                    compareWin.clampPos()
                }
            }
            Text {
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: "路线对比"
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 0.6
            }
            Text {
                objectName: "comparePaste"
                anchors.right: compareClearText.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: "粘贴"
                color: pasteMouse.containsMouse ? Theme.amber : Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 9
                MouseArea {
                    id: pasteMouse
                    anchors.fill: parent
                    anchors.margins: -4
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.comparePaste()
                }
            }
            Text {
                id: compareClearText
                objectName: "compareClear"
                anchors.right: compareClose.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: "清空"
                color: clearMouse.containsMouse ? Theme.danger : Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 9
                MouseArea {
                    id: clearMouse
                    anchors.fill: parent
                    anchors.margins: -4
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.compareClear()
                }
            }
            Item {
                id: compareClose
                objectName: "compareClose"
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 16
                height: 16
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: closeMouse.containsMouse ? Theme.danger : Theme.ink3
                    font.pixelSize: 11
                }
                MouseArea {
                    id: closeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.closeCompare()
                }
            }
        }

        // ---- 表头：怪 | 路线1 | 路线2 … ----
        Row {
            id: headRow
            x: 10
            y: 30
            spacing: 4
            visible: (host.compareRoutes || []).length > 0
            Text {
                width: compareWin.nameW
                text: "怪"
                color: Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 9
            }
            Repeater {
                model: host.compareRoutes || []
                Text {
                    objectName: "compareColName"
                    width: compareWin.routeW
                    text: modelData.label
                    color: Theme.ink2
                    font.family: Theme.uiFont
                    font.pixelSize: 9
                    elide: Text.ElideRight
                }
            }
        }

        // ---- 表体：一行一只怪 ----
        Flickable {
            id: compareFlick
            objectName: "compareFlick"
            x: 10
            y: 52
            width: parent.width - 20
            height: Math.max(40, compareCard.height - 52 - 30)
            contentWidth: width
            contentHeight: compareCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: compareCol
                width: compareFlick.width
                spacing: 2

                Repeater {
                    model: host.compareRows()
                    delegate: Row {
                        objectName: "compareRow"
                        width: compareCol.width
                        height: 20
                        spacing: 4
                        Text {
                            width: compareWin.nameW
                            text: (modelData.occurrence > 1
                                   ? modelData.name + " #" + modelData.occurrence
                                   : modelData.name)
                            color: Theme.ink
                            font.family: Theme.uiFont
                            font.pixelSize: 9
                            elide: Text.ElideRight
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Repeater {
                            model: modelData.damages
                            Text {
                                width: compareWin.routeW
                                text: modelData === null ? "—"
                                      : ("−" + host.fmt(modelData.damage))
                                color: (modelData === null ? Theme.ink3
                                       : (modelData.bad || modelData.lethal
                                          ? Theme.danger : Theme.ink))
                                font.family: Theme.monoFont
                                font.pixelSize: 9
                                elide: Text.ElideRight
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }
            }
        }

        // 空态提示（放在 Flickable 外面，不参与 Column 的高度）
        Text {
            objectName: "compareEmpty"
            visible: (host.compareRoutes || []).length === 0
            x: 10
            y: 52
            width: compareCard.width - 20
            text: "还没有路线。复制一条算好的路线（路线链上的「复制」/ Ctrl+C），\n"
                  + "再点「粘贴」；也可以把路线链上的「拖」拖进来。"
            color: Theme.ink3
            font.family: Theme.uiFont
            font.pixelSize: 9
            lineHeight: 1.4
        }

        // ---- 合计：总掉血 / 剩血 ----
        Row {
            id: totalRow
            objectName: "compareTotals"
            x: 10
            y: compareCard.height - 26
            spacing: 4
            visible: (host.compareRoutes || []).length > 0
            Text {
                width: compareWin.nameW
                text: "总掉血 / 剩血"
                color: Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 9
            }
            Repeater {
                model: host.compareTotals() || []
                Column {
                    width: compareWin.routeW
                    spacing: 0
                    Text {
                        objectName: "compareTotal"
                        text: modelData.total === undefined
                              ? "—" : host.fmt(modelData.total)
                        color: modelData.dead ? Theme.danger : Theme.ink
                        font.family: Theme.monoFont
                        font.pixelSize: 9
                        font.bold: true
                    }
                    Text {
                        objectName: "compareLeft"
                        text: modelData.hp === undefined
                              ? "" : ("剩 " + host.fmt(modelData.hp))
                        color: modelData.dead ? Theme.danger : Theme.ink3
                        font.family: Theme.uiFont
                        font.pixelSize: 8
                    }
                }
            }
        }

        // ---- 拖进来的路线（路线链上按住「拖」拖到这儿松手）----
        DropArea {
            objectName: "compareDrop"
            anchors.fill: parent
            keys: ["application/x-route-json"]
            onEntered: function (drag) { drag.accept() }
            onDropped: function (drop) {
                var text = drop.getDataAsString("application/x-route-json")
                host.compareDropRoute(text)
            }
        }

        // ---- 拉大小的手柄 ----
        CompareGrip {
            objectName: "compareGripTL"; pullLeft: true; pullTop: true
            anchors.left: parent.left; anchors.top: parent.top
            width: 12; height: 12
        }
        CompareGrip {
            objectName: "compareGripTR"; pullRight: true; pullTop: true
            anchors.right: parent.right; anchors.top: parent.top
            width: 12; height: 12
        }
        CompareGrip {
            objectName: "compareGripBL"; pullLeft: true; pullBottom: true
            anchors.left: parent.left; anchors.bottom: parent.bottom
            width: 12; height: 12
        }
        CompareGrip {
            objectName: "compareGrip"; pullRight: true; pullBottom: true
            anchors.right: parent.right; anchors.bottom: parent.bottom
            width: 18; height: 18
        }
        CompareGrip {
            objectName: "compareGripL"; pullLeft: true
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 5; height: Math.max(1, parent.height - 26)
        }
        CompareGrip {
            objectName: "compareGripR"; pullRight: true
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 5; height: Math.max(1, parent.height - 26)
        }
        CompareGrip {
            objectName: "compareGripT"; pullTop: true
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            height: 5; width: Math.max(1, parent.width - 26)
        }
        CompareGrip {
            objectName: "compareGripB"; pullBottom: true
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            height: 5; width: Math.max(1, parent.width - 26)
        }
    }
}
