import QtQuick

// 加怪 / 加资源下拉：挂在「＋ 加怪」「＋ 加资源」按钮下面。
//
// 「这一层」小窗的覆盖层（z=58）。条目和开关在主窗口上
// （`host.pickMode` / `host.pickFloor` / `host.pickMenuX/Y`），
// 要往哪一层加由 `sheetName` 递进来。
Item {
    id: pickMenuLayer

    // 归属：主窗口（状态都在它身上）
    property var host
    // 往哪一层加
    property string sheetName: ""
    objectName: "pickLayer"
    anchors.fill: parent
    // 只有"这扇窗自己的"菜单才画在这里
    visible: host.pickMode !== ""
             && String(host.pickFloor) === sheetName
    z: 58

    // 点菜单外面收起来
    MouseArea {
        anchors.fill: parent
        onClicked: host.pickMode = ""
    }

    Rectangle {
        id: pickCard
        objectName: "pickCard"
        x: host.pickMenuX
        y: host.pickMenuY
        width: 208
        radius: 8
        color: host.paperHi
        border.width: 1
        border.color: host.edge
        clip: true
        // 列表多高由小窗高度决定（见 openPickMenu）
     // 列表多高由小窗高度决定（见 openPickMenu）
    readonly property int listMax: host.pickListMax
        height: 26 + Math.min(pickCol.implicitHeight, listMax) + 8
        MouseArea { anchors.fill: parent }

        Text {
            x: 8
            y: 0
            height: 24
            verticalAlignment: Text.AlignVCenter
            text: host.pickReplaceIndex >= 0
                  ? "换成什么（" + (host.pickFloor || host.openFloor) + "）"
                  : (host.pickMode === "mon"
                     ? "加怪到 " + (host.pickFloor || host.openFloor)
                     : "加资源到 " + (host.pickFloor || host.openFloor))
            color: host.ink3
            font.family: host.uiFont
            font.pixelSize: 9
            elide: Text.ElideRight
            width: pickCard.width - 16
        }

        Flickable {
            x: 4
            y: 26
            width: pickCard.width - 8
            height: Math.min(pickCol.implicitHeight, pickCard.listMax)
            contentWidth: width
            contentHeight: pickCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: pickCol
                width: parent.width
                spacing: 0

                Repeater {
                    model: host.pickMode === "mon" ? host.monChoices()
                         : (host.pickMode === "item" ? host.itemChoices() : [])
                    delegate: Rectangle {
                        objectName: "pickRow"
                        width: pickCol.width
                        height: 28
                        radius: 6
                        color: pickMouse.containsMouse ? host.paperLo : "transparent"

                        Image {
                            id: pickIcon
                            x: 4
                            anchors.verticalCenter: parent.verticalCenter
                            width: 18
                            height: 18
                            // 资源的 icon 是"文件名干"，要拼成 assets 下的真路径
                            source: host.pickMode === "item"
                                    ? host.itemIcon(modelData && modelData.icon
                                                   ? modelData.icon : "")
                                    : (modelData && modelData.icon
                                       ? modelData.icon : "")
                            visible: source !== ""
                            fillMode: Image.PreserveAspectFit
                            smooth: false
                        }
                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: pickIcon.visible ? 28 : 8
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData
                                  ? (modelData.effect
                                     ? modelData.name + "  " + modelData.effect
                                     : modelData.name)
                                  : ""
                            color: host.ink
                            font.family: host.uiFont
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }
                        MouseArea {
                            id: pickMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: host.pickRow(modelData)
                        }
                    }
                }

                Text {
                    width: pickCol.width
                    height: 28
                    visible: host.pickMode !== ""
                             && (host.pickMode === "mon"
                                 ? host.monChoices().length === 0
                                 : host.itemChoices().length === 0)
                    text: host.pickMode === "mon"
                          ? "手册里还没有怪，先读一次怪物手册。"
                          : "还没有可加的资源。"
                    color: host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 10
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
