import QtQuick
import "../shared"

// 技能那一张卡：按地图上出现过的怪统计，每个技能涉及几只、还剩几只。
// 一个技能一颗胶囊（「吸血 2/2」= 技能名 + 剩余/总数），放不下自动换行。
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
    Item { width: parent.width; height: 2 }

    Flow {
        id: chips
        width: parent.width
        spacing: 6
        // 技能这张卡折叠起来时整排让位（Column 会跳过不可见的子项）
        visible: !host.skillCollapsed
        // 一排胶囊上下留一点，别贴着标题
        bottomPadding: host.skills.length > 0 ? 2 : 0

        Repeater {
            model: host.skills
            delegate: Rectangle {
                objectName: "skillRow"
                height: 26
                radius: 13
                width: skillInner.width + 20
                color: Theme.tile

                Row {
                    id: skillInner
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        objectName: "skillName"
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData ? modelData.name : ""
                        color: Theme.ink
                        font.family: Theme.uiFont
                        font.pixelSize: 12
                    }
                    // 剩余/总数：还有就是强调蓝，打光了变灰
                    Text {
                        objectName: "skillLeft"
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData ? modelData.left + "/" + modelData.total : ""
                        color: modelData && modelData.left > 0 ? Theme.amber : Theme.ink3
                        font.family: Theme.monoFont
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
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
