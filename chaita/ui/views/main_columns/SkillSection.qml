import QtQuick
import QtQuick.Controls.Basic
import "../shared"

// 技能那一张卡：按地图上出现过的怪统计，每个技能涉及几只、还剩几只。
// 一个技能一颗胶囊（「吸血 2/2」= 技能名 + 剩余/总数），放不下自动换行。
//
// 点一颗胶囊 → 弹出这个技能的介绍卡：
//   · 内置的常见技能：游戏手册原话（只读的底），可以改写 —— 不同的魔塔数值可能不同，
//     改写的存进 skill_notes.json、优先显示，「恢复原话」一键还原；
//   · 内置表里没有的技能：一个空白文本框，用户自己写；
//   · 下面列出带这个技能的怪（每只怪自己记的数值）。
Card {
    id: section
    objectName: "skillSectionCard"

    // 归属：主窗口
    property var host

    // 介绍卡现在开着的是哪个技能（"" = 没开）、它的介绍状态、胶囊的位置
    property string introSkill: ""
    property var introInfo: ({ "text": "", "source": "", "hasBuiltin": false, "edited": false })
    property point introAnchor: Qt.point(0, 0)         // 胶囊下沿，在窗口坐标里
    property real introAnchorTop: 0                    // 胶囊上沿（下面放不下就翻到上面）

    // 这个技能的统计行（总数/剩余），点开时拿来写在卡的标题上
    function rowOf(name) {
        var list = host.skills || []
        for (var i = 0; i < list.length; i++) {
            if ((list[i] || {}).name === name)
                return list[i]
        }
        return null
    }

    // 带这个技能的怪：一只一行，带**这只怪自己的**数值
    function membersOf(name) {
        var stats = (controller ? controller.skillStats : null) || []
        for (var i = 0; i < stats.length; i++) {
            if ((stats[i] || {}).skill === name)
                return stats[i].mons || []
        }
        return []
    }

    // 重新读一遍这个技能的介绍（打开时、存完、恢复原话后都要）
    function refreshIntro() {
        if (section.introSkill === "" || !controller)
            return
        section.introInfo = controller.skillIntro(section.introSkill)
        noteEdit.text = section.introInfo.text
    }

    function openIntro(name, chip) {
        var below = chip.mapToItem(Overlay.overlay, 0, chip.height + 6)
        section.introAnchor = Qt.point(below.x, below.y)
        section.introAnchorTop = below.y - chip.height - 12
        section.introSkill = name
        section.refreshIntro()
        intro.open()
    }

    // 文本框里的字和已存的不一样才存（空 / 和原话一样 = 恢复原话，由 controller 判断）
    function commitIntro() {
        if (section.introSkill === "" || !controller)
            return
        if (noteEdit.text.trim() === String(section.introInfo.text || "").trim())
            return
        controller.setSkillNote(section.introSkill, noteEdit.text)
        section.refreshIntro()
    }

    Connections {
        target: controller
        function onSkillStatsChanged() {
            if (intro.opened)
                section.refreshIntro()
        }
    }

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
                id: chip
                objectName: "skillRow"
                readonly property bool open: intro.opened
                                             && section.introSkill === (modelData ? modelData.name : "")
                height: 26
                radius: 13
                width: skillInner.width + 20
                color: chip.open ? Theme.accentSoft
                     : (chipMouse.containsMouse ? Theme.hover : Theme.tile)
                Behavior on color { ColorAnimation { duration: 100 } }

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
                        color: modelData && modelData.left > 0 ? Theme.accent : Theme.ink3
                        font.family: Theme.monoFont
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
                MouseArea {
                    id: chipMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: section.openIntro(modelData.name, chip)
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

    // ---------- 技能介绍卡 ----------
    Popup {
        id: intro
        objectName: "skillIntro"
        parent: Overlay.overlay
        width: Math.min(300, Overlay.overlay.width - 24)
        padding: 12
        focus: true
        modal: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        // 摆在胶囊下面；放不下就翻到胶囊上面；左右都夹在窗口里
        x: Math.max(12, Math.min(section.introAnchor.x,
                                 Overlay.overlay.width - width - 12))
        y: section.introAnchor.y + implicitHeight > Overlay.overlay.height - 12
           ? Math.max(12, section.introAnchorTop - implicitHeight)
           : section.introAnchor.y

        // Esc 只关这张卡，别让它顺手把整个软件关了（主窗口的 Esc 看这个开关）
        onOpened: host.skillIntroOpen = true
        onClosed: {
            section.commitIntro()
            section.introSkill = ""
            host.skillIntroOpen = false
        }

        background: Rectangle {
            radius: 10
            color: Theme.paper
            border.width: 1
            border.color: Theme.cardEdge
            // 底沿一线暗边，和其他卡同一个长相
            Rectangle {
                z: -1
                anchors.fill: parent
                anchors.topMargin: 2
                anchors.bottomMargin: -1
                radius: parent.radius
                color: Theme.cardShade
            }
        }

        contentItem: Column {
            spacing: 8

            // 标题：技能名 + 剩余/总数
            Item {
                width: parent.width
                height: 22
                Text {
                    objectName: "skillIntroName"
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: section.introSkill
                    color: Theme.ink
                    font.family: Theme.uiFont
                    font.pixelSize: 14
                    font.bold: true
                }
                Chip {
                    readonly property var one: section.rowOf(section.introSkill)
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    height: 20
                    visible: !!one
                    tone: one && one.left > 0 ? "accent" : "muted"
                    text: one ? "剩 " + one.left + "/" + one.total : ""
                    mono: true
                    fontSize: 11
                }
            }

            // 效果：来源标签 + 可编辑的文字
            Item {
                width: parent.width
                height: 16
                Text {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "效果"
                    color: Theme.ink3
                    font.family: Theme.uiFont
                    font.pixelSize: 11
                }
                Row {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 10
                    Text {
                        objectName: "skillIntroSource"
                        anchors.verticalCenter: parent.verticalCenter
                        text: section.introInfo.edited ? "已改写"
                            : (section.introInfo.source === "builtin" ? "手册原话"
                            : (section.introInfo.source === "" ? "还没有介绍" : "自己写的"))
                        color: Theme.ink3
                        font.family: Theme.uiFont
                        font.pixelSize: 10
                    }
                    // 改写过才有：一键还原成手册原话
                    TextBtn {
                        objectName: "skillIntroRestore"
                        visible: !!section.introInfo.edited
                        text: "恢复原话"
                        accent: Theme.accent
                        onClicked: {
                            controller.setSkillNote(section.introSkill, "")
                            section.refreshIntro()
                        }
                    }
                }
            }

            TextArea {
                id: noteEdit
                objectName: "skillIntroEffect"
                width: parent.width
                height: Math.max(56, implicitHeight)
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 12
                padding: 8
                placeholderText: "还没有介绍。写下它的效果，比如：被击中后…"
                placeholderTextColor: Theme.ink3
                background: Rectangle {
                    radius: 6
                    color: Theme.tile
                    border.width: 1
                    border.color: noteEdit.activeFocus ? Theme.accent : "transparent"
                }
                // 改完点别处就存
                onActiveFocusChanged: if (!activeFocus) section.commitIntro()
            }

            // 带这个技能的怪：一只一行
            Text {
                visible: section.membersOf(section.introSkill).length > 0
                text: "带这个技能的怪"
                color: Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 11
            }
            Column {
                width: parent.width
                spacing: 4
                Repeater {
                    model: section.membersOf(section.introSkill)
                    delegate: Item {
                        objectName: "skillIntroMonster"
                        width: parent.width
                        height: 20
                        Text {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.name
                            color: Theme.ink
                            font.family: Theme.uiFont
                            font.pixelSize: 12
                        }
                        Row {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8
                            // 这只怪自己记的数值（同名技能在不同层可能不一样）
                            Text {
                                visible: !!modelData.value
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.value
                                color: Theme.accent
                                font.family: Theme.monoFont
                                font.pixelSize: 11
                            }
                            Text {
                                visible: !!modelData.count
                                anchors.verticalCenter: parent.verticalCenter
                                text: "×" + modelData.count
                                color: Theme.ink3
                                font.family: Theme.monoFont
                                font.pixelSize: 11
                            }
                        }
                    }
                }
            }
        }
    }
}
