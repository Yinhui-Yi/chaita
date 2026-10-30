import QtQuick
import QtQuick.Controls.Basic
// 先看 docs/UI_MAP.md / docs/ROUTE.md。这一份 = 路线链里"这一格填什么"的下拉。
//
// 路线链窗口的覆盖层（z=20）。状态在主窗口上（`ctx.menu` /
// `ctx.menuCell` / `ctx.pickTab` / `ctx.pickData`），
// 这里只画列表、响应点击。两个标签页（怪物 / 资源）+ 两个动作（门 / 清空）：
// 「门」是走过不掉血的那种格子（用户："每格点开填这一格有什么（怪/资源/门）"）。
import "../../shared"

Item {
    id: routeMenuLayer

    // 归属：主窗口（状态都在它身上）
    property var host
    property var ctx: ({})
    // 选项列表最多多高：窗口那边按"这一格上面/下面还剩多少地方"给（菜单不能出窗）
    property real maxListH: 240
    objectName: "routeMenu"
    anchors.fill: parent
    visible: ctx.menu !== ""
    z: 20

    function cell() {
        var cells = ctx.cells || []
        var index = Number(ctx.menuCell)
        return (index >= 0 && index < cells.length) ? (cells[index] || ({})) : ({})
    }

    // 菜单实际多高：窗口那边按它决定挂在格子下面还是上面
    function menuHeight() {
        return routeMenuCard.height
    }

    MouseArea {
        anchors.fill: parent
        onClicked: host.closeRouteMenu(ctx)
    }

    Rectangle {
        id: routeMenuCard
        objectName: "routeMenuCard"
        x: ctx.menuX
        y: ctx.menuY
        width: 250
        // 标题 22 + 标签页 26 + 列表 + 动作 26 + 留白
        readonly property real listH:
            Math.min(240, Math.min(maxListH, routeMenuCol.implicitHeight))
        height: 52 + listH + 32
        radius: 8
        color: Theme.paperHi
        border.width: 1
        border.color: Theme.edge
        clip: true
        MouseArea { anchors.fill: parent }

        Text {
            objectName: "routeMenuTitle"
            x: 8
            y: 0
            width: parent.width - 16
            height: 22
            verticalAlignment: Text.AlignVCenter
            text: "这一格有什么：" + host.routeLabel(routeMenuLayer.cell())
            color: Theme.ink3
            font.family: Theme.uiFont
            font.pixelSize: 9
            elide: Text.ElideRight
        }

        // 两个标签页：怪物 / 资源（和伤害计算的下拉同一个规矩）
        Row {
            x: 6
            y: 24
            spacing: 4

            Rectangle {
                objectName: "routeTabMonster"
                width: 52
                height: 22
                radius: 11
                color: ctx.pickTab === "monster"
                       ? Theme.paperLo : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "怪物"
                    color: ctx.pickTab === "monster"
                           ? Theme.ink : Theme.ink3
                    font.family: Theme.uiFont
                    font.pixelSize: 10
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.routeSwitchTab(ctx, "monster")
                }
            }

            Rectangle {
                objectName: "routeTabItem"
                width: 52
                height: 22
                radius: 11
                color: ctx.pickTab === "item"
                       ? Theme.paperLo : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "资源"
                    color: ctx.pickTab === "item"
                           ? Theme.ink : Theme.ink3
                    font.family: Theme.uiFont
                    font.pixelSize: 10
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.routeSwitchTab(ctx, "item")
                }
            }
        }

        Flickable {
            objectName: "routeMenuFlick"
            x: 4
            y: 52
            width: routeMenuCard.width - 8
            height: routeMenuCard.listH
            contentWidth: width
            contentHeight: routeMenuCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: routeMenuCol
                width: parent.width
                spacing: 0

                Text {
                    objectName: "routeMenuEmpty"
                    visible: (ctx.pickData || []).length === 0
                    width: routeMenuCol.width
                    height: visible ? 46 : 0
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: ctx.pickTab === "item"
                          ? "没有能算加成的资源"
                          : "手册里还没有怪，先读一次怪物手册"
                    color: Theme.ink3
                    font.family: Theme.uiFont
                    font.pixelSize: 9
                    wrapMode: Text.WordWrap
                }

                Repeater {
                    model: ctx.pickData || []
                    delegate: Rectangle {
                        objectName: "routePickRow"
                        width: routeMenuCol.width
                        height: 26
                        radius: 5
                        color: pickMouse.containsMouse
                               ? Theme.paperLo : "transparent"
                        MouseArea {
                            id: pickMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: host.routeFill(ctx, ctx.menuCell,
                                                      modelData.entry,
                                                      modelData.kind)
                        }
                        Image {
                            x: 4
                            width: 18
                            height: 18
                            anchors.verticalCenter: parent.verticalCenter
                            source: host.routeRowIcon(modelData.kind,
                                                      modelData.entry.icon)
                            visible: source !== ""
                            fillMode: Image.PreserveAspectFit
                            smooth: false
                        }
                        Text {
                            x: 26
                            width: parent.width - 32
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.kind === "item"
                                ? (modelData.entry.name + "   "
                                   + modelData.entry.effect)
                                : (modelData.entry.name + "   "
                                   + modelData.entry.hp + "/"
                                   + modelData.entry.atk + "/"
                                   + modelData.entry.def
                                   + (modelData.entry.skillsText
                                      ? "   " + modelData.entry.skillsText
                                      : ""))
                            color: Theme.ink
                            font.family: Theme.uiFont
                            font.pixelSize: 9
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        // 两个动作：门（走过、不掉血）/ 清空这一格
        Row {
            x: 6
            y: 52 + routeMenuCard.listH + 4
            spacing: 6

            FlatBtn {
                objectName: "routeCellDoor"
                label: "门（不掉血）"
                onClicked: host.routeFill(ctx, ctx.menuCell, null, "door")
            }

            FlatBtn {
                objectName: "routeCellClear"
                label: "清空"
                danger: true
                onClicked: host.routeFill(ctx, ctx.menuCell, null, "")
            }
        }
    }
}
