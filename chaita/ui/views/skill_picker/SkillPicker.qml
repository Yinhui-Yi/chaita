import QtQuick

// 技能挑选下拉：点「加技能」弹出来，列自定义 + 手册里的技能。
//
// 主窗口的覆盖层（z=72），一个界面一个文件夹（views/skill_picker/）。
// 开关在 host 上（`host.skillPicker`）：Esc 关最上面那层由主窗口统一判断，
// 这里只管自己的列表、定位和选中；选中走 `pick()`。
Item {
    id: skillPickerLayer

    // 主窗口（原来直接叫 win）
    property var host
    objectName: "skillPicker"
    anchors.fill: parent
    visible: host.skillPicker
    z: 72

    // 点菜单外面就收起来
    MouseArea {
        anchors.fill: parent
        onClicked: host.skillPicker = false
    }

    Rectangle {
        id: skillCard
        objectName: "skillCard"
        x: host.skillMenuX
        y: host.skillMenuY
        width: 170
        radius: 8
        color: host.paperHi
        border.width: 1
        border.color: host.edge
        clip: true
        readonly property int listMax: 200
        height: 28 + Math.min(skillCol.implicitHeight, listMax) + 8
        MouseArea { anchors.fill: parent }

        Text {
            x: 8
            y: 0
            height: 26
            verticalAlignment: Text.AlignVCenter
            text: "加技能"
            color: host.ink3
            font.family: host.uiFont
            font.pixelSize: 9
            font.letterSpacing: 1
        }

        Flickable {
            x: 4
            y: 28
            width: skillCard.width - 8
            height: Math.min(skillCol.implicitHeight, skillCard.listMax)
            contentWidth: width
            contentHeight: skillCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: skillCol
                width: parent.width
                spacing: 0
                // 第一项：自己写（原来那个「＋ 加」按钮）
                Rectangle {
                    objectName: "skillPickCustom"
                    width: skillCol.width
                    height: 26
                    radius: 6
                    color: customPickMouse.containsMouse ? host.paperLo
                                                         : "transparent"
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        text: "自定义…"
                        color: host.ink
                        font.family: host.uiFont
                        font.pixelSize: 10
                    }
                    MouseArea {
                        id: customPickMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: pick("")
                    }
                }
                Rectangle {
                    width: skillCol.width
                    height: 1
                    color: host.hairline
                }
                Repeater {
                    model: host.skillNames()
                    delegate: Rectangle {
                        objectName: "skillPickRow"
                        width: skillCol.width
                        height: 26
                        radius: 6
                        color: skillPickMouse.containsMouse
                               ? host.paperLo : "transparent"
                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData
                            color: host.ink
                            font.family: host.uiFont
                            font.pixelSize: 10
                        }
                        MouseArea {
                            id: skillPickMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: pick(modelData)
                        }
                    }
                }
            }
        }
    }

    // 选中一个技能（空串 = 自定义）；选中就关掉下拉
    function pick(name) {
        host.addSkill(name)
        host.skillPicker = false
    }

    // 按「加技能」按钮的位置摆（box = 按钮在窗口里的矩形）。
    // 摆哪由这里算：它知道自己多高，主窗口不用再按行数估一个高度出来。
    function placeUnder(box) {
        var w = skillCard.width
        var h = skillCard.height
        var top = box.y + box.height + 4
        if (top + h > host.height - 8)
            top = Math.max(8, box.y - h - 8)
        host.skillMenuY = top
        host.skillMenuX = Math.max(8, Math.min(host.width - 8 - w,
                                              box.x + box.width - w))
    }
}
