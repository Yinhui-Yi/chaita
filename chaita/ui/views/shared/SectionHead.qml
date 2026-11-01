import QtQuick
import "."

// 分区标题条：小三角 + 标题，点一下折叠/展开；右边留一个槽放聚合数字、读取按钮之类。
// 主界面的「地图 / 怪物 / 技能」三栏共用（原来每栏各抄一份，样式很容易走散）。
//
// 命名规矩（测试和预览按名字找）：key 是 "map" / "mon" / "skill"，
// 整条标题 = key + "SectionHead"，三角 = key + "Chevron"，文字 = key + "SectionLabel"。
Item {
    id: head

    // 分区的短名（拼 objectName 用）
    property string key: ""
    property string title: ""
    property bool collapsed: false
    // 右边的内容（右对齐，垂直居中）
    default property alias rightContent: rightRow.data
    signal toggled()

    height: 28

    Item {
        id: toggle
        objectName: head.key + "SectionHead"
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: label.x + label.width + 8
        height: parent.height

        Text {
            objectName: head.key + "Chevron"
            anchors.verticalCenter: parent.verticalCenter
            width: 12
            text: head.collapsed ? "▸" : "▾"
            color: toggleMouse.containsMouse ? Theme.amber : Theme.ink3
            font.pixelSize: 10
        }
        Text {
            id: label
            objectName: head.key + "SectionLabel"
            x: 14
            anchors.verticalCenter: parent.verticalCenter
            text: head.title
            color: Theme.ink
            font.family: Theme.uiFont
            font.pixelSize: 12
            font.bold: true
        }
        MouseArea {
            id: toggleMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: head.toggled()
        }
    }

    Row {
        id: rightRow
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.hairline
    }
}
