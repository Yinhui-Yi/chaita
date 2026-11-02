import QtQuick
import QtQuick.Controls.Basic
import "../shared"

// 路线那一张卡：所有层的路线统一列在这里（跨层路线存在起点层名下，每格带自己的层，
// 单看一层的清单看不全，所以不再放在「这一层」里）。
//
// 一条路线两行：
//   第一行  路线 N · 起点层 → 终点层（只经过一层就只写层号）· 「跨 N 层」胶囊 · ✕
//   第二行  走完之后的 血/攻/防/魔防（实时算，只读）· 备注（可改，回车保存）
// 点第一行 = 打开这条路线的链窗口。数据全在 controller.allRoutes()，这里只画和点。
Card {
    id: section
    objectName: "routeSectionCard"

    // 归属：主窗口
    property var host

    // 一条路线多高 / 最多露几条（再多在卡里滚动，别把主窗口撑爆）
    readonly property int rowH: 48
    readonly property int maxRows: 4

    // 读一下 mapHistory 让路线改了就重列（controller 的路线都存在层记录里）
    readonly property var rows: {
        if (!controller)
            return []
        controller.mapHistory
        return controller.allRoutes() || []
    }

    SectionHead {
        width: parent.width
        key: "route"
        title: "路线"
        collapsed: host.routeCollapsed
        onToggled: controller.setRouteCollapsed(!host.routeCollapsed)

        Text {
            objectName: "routeAgg"
            anchors.verticalCenter: parent.verticalCenter
            text: section.rows.length > 0 ? (section.rows.length + " 条") : ""
            color: Theme.ink3
            font.family: Theme.monoFont
            font.pixelSize: 10
        }
    }
    Item { width: parent.width; height: 2; visible: !host.routeCollapsed }

    Text {
        objectName: "routeCardEmpty"
        width: parent.width
        height: visible ? 28 : 0
        visible: !host.routeCollapsed && section.rows.length === 0
        verticalAlignment: Text.AlignVCenter
        text: "在地图上长按玩家，拖出一条路线。"
        color: Theme.ink3
        font.family: Theme.uiFont
        font.pixelSize: 11
    }

    Flickable {
        id: flick
        objectName: "routeCardFlick"
        width: parent.width
        height: Math.min(col.implicitHeight, section.rowH * section.maxRows)
        visible: !host.routeCollapsed && section.rows.length > 0
        contentWidth: width
        contentHeight: col.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: col
            width: flick.width

            Repeater {
                model: section.rows
                delegate: Item {
                    id: row
                    objectName: "routeRow"
                    width: col.width
                    height: section.rowH

                    readonly property var info: modelData || ({})
                    readonly property bool cross: Number(info.floors) > 1
                    // 同一层只写那一层；跨层写「起点 → 终点」
                    readonly property string where: cross
                        ? host.floorShort(info.start) + "层 → " + host.floorShort(info.end) + "层"
                        : host.floorShort(info.start) + "层"

                    Rectangle {
                        anchors.fill: parent
                        anchors.bottomMargin: 4
                        radius: Theme.radius
                        color: openMouse.containsMouse ? Theme.tile : "transparent"
                    }
                    // 两条路线之间一条细线
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.hairline
                        visible: index < section.rows.length - 1
                    }

                    // 第一行：点它打开链窗口
                    MouseArea {
                        id: openMouse
                        objectName: "routeOpen"
                        x: 0
                        y: 0
                        width: parent.width - 28
                        height: 24
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: host.openRoute(row.info.floor, row.info.index)
                    }
                    Row {
                        x: 4
                        y: 0
                        height: 24
                        spacing: 8
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "路线 " + (index + 1)
                            color: openMouse.containsMouse ? Theme.accent : Theme.ink
                            font.family: Theme.uiFont
                            font.pixelSize: 12
                            font.bold: true
                        }
                        Text {
                            objectName: "routeWhere"
                            anchors.verticalCenter: parent.verticalCenter
                            text: row.where
                            color: Theme.ink2
                            font.family: Theme.uiFont
                            font.pixelSize: 11
                        }
                        Chip {
                            objectName: "routeCross"
                            anchors.verticalCenter: parent.verticalCenter
                            visible: row.cross
                            tone: "accent"
                            text: "跨 " + row.info.floors + " 层"
                        }
                    }
                    IconBtn {
                        objectName: "routeRowDelete"
                        anchors.right: parent.right
                        y: 0
                        width: 24
                        height: 24
                        glyph: "✕"
                        glyphSize: 11
                        hoverInk: Theme.danger
                        hoverBack: Theme.dangerSoft
                        onClicked: controller.removeRoute(row.info.floor, row.info.index)
                    }

                    // 第二行：数值（只读）+ 备注
                    Text {
                        id: stats
                        objectName: "routeComputed"
                        x: 4
                        y: 24
                        width: 160
                        height: 20
                        verticalAlignment: Text.AlignVCenter
                        text: host.routeStatsFor(row.info.floor, row.info.index)
                        color: Theme.ink3
                        font.family: Theme.monoFont
                        font.pixelSize: 10
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        x: stats.x + stats.width + 6
                        y: 24
                        width: row.width - x - 2
                        height: 20
                        radius: Theme.radius
                        color: memoField.activeFocus ? Theme.paper : Theme.tile
                        border.width: 1
                        border.color: memoField.activeFocus ? Theme.accent : "transparent"
                        TextField {
                            id: memoField
                            objectName: "routeMemo"
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 6
                            verticalAlignment: TextInput.AlignVCenter
                            background: null
                            padding: 0
                            color: Theme.ink
                            placeholderText: "备注"
                            placeholderTextColor: Theme.ink3
                            font.family: Theme.uiFont
                            font.pixelSize: 11
                            selectByMouse: true
                            text: row.info.memo
                            onEditingFinished: controller.saveRouteMemo(
                                row.info.floor, row.info.index, text)
                        }
                    }
                }
            }
        }
    }
}
