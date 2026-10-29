import QtQuick
import QtQuick.Controls.Basic

// 问号菜单：这一行要加什么 —— 两个标签页「怪物 / 资源」。
//
// 伤害计算窗口的覆盖层（z=20）。状态在主窗口上（`host.battleMenu` /
// `host.battleMenuPlan` / `host.battlePickTab` / `host.battlePickData`），
// 这里只画列表、响应点击。
Item {
    id: battleMenuLayer

    // 归属：主窗口（状态都在它身上）
    property var host
    objectName: "battleMenu"
    anchors.fill: parent
    visible: host.battleMenu !== ""
    z: 20

    MouseArea {
        anchors.fill: parent
        onClicked: host.battleMenu = ""
    }

    Rectangle {
        id: battleMenuCard
        objectName: "battleMenuCard"
        x: host.battleMenuX
        y: host.battleMenuY
        width: 250
        radius: 8
        color: host.paperHi
        border.width: 1
        border.color: host.edge
        clip: true
        height: 56 + Math.min(battleMenuCol.implicitHeight, 240) + 8
        MouseArea { anchors.fill: parent }

        Text {
            objectName: "battleMenuTitle"
            x: 8
            y: 0
            height: 24
            verticalAlignment: Text.AlignVCenter
            text: "第 " + (host.battleMenuPlan + 1) + " 行："
                  + (host.battleMenuInsert >= 0
                     ? "插在第 " + (host.battleMenuInsert + 1)
                       + " 格前面"
                     : "接在最后")
            color: host.ink3
            font.family: host.uiFont
            font.pixelSize: 9
        }

        // 两个标签页：怪物 / 资源（用户："应该只有两个标签页分别是
        // 怪物和资源（包含 4 色宝石）"）。选中的那个戴浅色胶囊底。
        Item {
            id: battleTabs
            x: 6
            y: 26
            width: battleMenuCard.width - 12
            height: 24

            Row {
                spacing: 4

                Rectangle {
                    objectName: "battleTabMonster"
                    width: 52
                    height: 22
                    radius: 11
                    color: host.battlePickTab === "monster"
                           ? host.paperLo : "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: "怪物"
                        color: host.battlePickTab === "monster"
                               ? host.ink : host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 10
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: host.battleSwitchTab("monster")
                    }
                }

                Rectangle {
                    objectName: "battleTabItem"
                    width: 52
                    height: 22
                    radius: 11
                    color: host.battlePickTab === "item"
                           ? host.paperLo : "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: "资源"
                        color: host.battlePickTab === "item"
                               ? host.ink : host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 10
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: host.battleSwitchTab("item")
                    }
                }
            }
        }

        Flickable {
            objectName: "battleMenuFlick"
            x: 4
            y: 56
            width: battleMenuCard.width - 8
            height: Math.min(battleMenuCol.implicitHeight, 240)
            contentWidth: width
            contentHeight: battleMenuCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: battleMenuCol
                width: parent.width
                spacing: 0

                // 这一页空了就给一句说明（比如还没读过手册）
                Text {
                    objectName: "battleMenuEmpty"
                    visible: (host.battlePickData || []).length === 0
                    width: battleMenuCol.width
                    height: visible ? 46 : 0
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: host.battlePickTab === "item"
                          ? "没有能算加成的资源"
                          : "手册里还没有怪，先读一次怪物手册"
                    color: host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 9
                    wrapMode: Text.WordWrap
                }

                Repeater {
                    model: host.battlePickData || []
                    delegate: Rectangle {
                        objectName: "battlePickRow"
                        width: battleMenuCol.width
                        height: 26
                        radius: 5
                        color: battlePickMouse.containsMouse
                               ? host.paperLo : "transparent"
                        MouseArea {
                            id: battlePickMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: host.battleFillRow(
                                host.battleMenuPlan,
                                modelData.entry, modelData.kind,
                                host.battleMenuInsert)
                        }
                        Image {
                            x: 4
                            width: 18
                            height: 18
                            anchors.verticalCenter: parent.verticalCenter
                            source: host.battleStepIcon({
                                "kind": modelData.kind,
                                "icon": modelData.entry.icon })
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
                            color: host.ink
                            font.family: host.uiFont
                            font.pixelSize: 9
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }
}
