import QtQuick
import "../shared"

// 技能那一张卡：按地图上出现过的怪统计，每个技能涉及几只、还剩几只。
Card {
    id: section
    objectName: "skillSectionCard"

    // 归属：主窗口
    property var host

    SectionHead {
        width: parent.width
        key: "skill"
        title: "技能"
        collapsed: host.skillCollapsed
        onToggled: host.toggleSkillSection()

        Text {
            objectName: "skillAgg"
            anchors.verticalCenter: parent.verticalCenter
            text: host.skillAgg
            color: Theme.ink3
            font.family: Theme.monoFont
            font.pixelSize: 10
        }
    }
    Item { width: parent.width; height: 4 }

    Repeater {
        model: host.skills
        delegate: Item {
            objectName: "skillRow"
            width: parent.width
            height: 36
            // 技能这张卡折叠起来时整行让位（Column 会跳过不可见的子项）
            visible: !host.skillCollapsed
            Text {
                objectName: "skillName"
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: modelData ? modelData.name : ""
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 13
            }
            Chip {
                objectName: "skillLeft"
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                tone: modelData && modelData.left > 0 ? "accent" : "muted"
                mono: true
                text: modelData
                      ? modelData.total + " 只 · 剩 " + modelData.left : ""
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.hairline
            }
        }
    }
    Text {
        width: parent.width
        height: visible ? 28 : 0
        visible: host.skills.length === 0 && !host.skillCollapsed
        verticalAlignment: Text.AlignVCenter
        text: "还没读到技能。"
        color: Theme.ink3
        font.family: Theme.uiFont
        font.pixelSize: 11
    }
}
