import QtQuick
import QtQuick.Controls.Basic
// 共用件（FlatBtn / Theme）在上一层目录
import "../shared"

// 怪物编辑：改这一只的血/攻/防、数量、技能参数、缩略图。
//
// 主窗口的**覆盖层**（z=60），一个界面一个文件夹（views/monster_editor/）。
// 为什么是浮起来的卡片而不是铺满：铺满会把游戏画面和下面那串怪一起盖掉，
// 还看不出在改哪一只（用户："修改窗口要居中"）。
//
// 状态在主窗口上：`host.monEdit`（第几只，-1 = 关着）、`host.monDraft`（草稿）、
// `host.monSkills`、`host.monIconUrl`；这里只画和改草稿。
Item {
    id: monDialog
    // 主窗口（原来直接叫 win）
    property var host

    // 自己那几个输入框的「灌草稿 / 收草稿」：原来在主窗口里、跨文件抓
    // headerName、fldHp 这些内部 id —— 那就等于没模块化，现在归这扇界面自己管。

    // 头像框在场景里的位置和大小：素材库选图要贴着它摆。
    // 主窗口问这里要（别跨文件摸 monIconBox 这个内部 id）。
    function iconAnchorBox() {
        var at = monIconBox.mapToItem(null, 0, 0)
        return { "x": at.x, "y": at.y,
                 "width": monIconBox.width, "height": monIconBox.height }
    }

    // 「加技能」按钮在场景里的矩形：技能下拉贴着它摆（同 iconAnchorBox 的规矩）
    function skillAnchorBox() {
        var at = skillBtn.mapToItem(null, 0, 0)
        return { "x": at.x, "y": at.y,
                 "width": skillBtn.width, "height": skillBtn.height }
    }

    // 打开时把草稿灌进输入框（输入框是"单向"的：用户改完回车/失焦才写回草稿）
    function fill() {
        headerName.text = host.draftValue("name")
        fldHp.field.text = host.draftValue("hp")
        fldAtk.field.text = host.draftValue("atk")
        fldDef.field.text = host.draftValue("def")
        fldGold.field.text = host.draftValue("gold")
        fldExp.field.text = host.draftValue("exp")
    }

    // 点「保存」先把手里的字收进草稿，再落盘（用户可能没按回车就直接点保存）
    function commit() {
        host.setDraft("name", headerName.text)
        host.setDraft("hp", fldHp.field.text)
        host.setDraft("atk", fldAtk.field.text)
        host.setDraft("def", fldDef.field.text)
        host.setDraft("gold", fldGold.field.text)
        host.setDraft("exp", fldExp.field.text)
        host.saveMonster()
    }
    objectName: "monEditDialog"
    anchors.fill: parent
    visible: host.monEdit >= 0
    z: 60

    // 点卡片外面关掉。**这一层不画东西**（弹层一律不压暗）
    MouseArea {
        anchors.fill: parent
        onClicked: host.closeMonster()
    }

    Rectangle {
        id: monCard
        objectName: "monEditCard"
        // 居中都夹回窗口里，窄窗口/矮窗口也顶不出去
        readonly property int cardW: Math.min(300, monDialog.width - 16)
        readonly property int cardMaxH: Math.max(160, monDialog.height - 16)
        // 卡片里能滚多高：总高扣掉抬头（50）和底部按钮（44）
        readonly property int bodyMax: Math.max(
            80, monCard.cardMaxH - 50 - 44)
        x: host.monCardX >= 0
           ? Math.max(0, Math.min(monDialog.width - width, host.monCardX))
           : Math.max(8, (monDialog.width - width) / 2)
        y: host.monCardY >= 0
           ? Math.max(0, Math.min(monDialog.height - height, host.monCardY))
           : Math.max(8, (monDialog.height - height) / 2)
        width: cardW
        height: Math.min(cardMaxH, 50 + monFlick.height + 44)
        radius: 8
        color: host.paperHi
        border.width: 1
        border.color: host.edge
        // 背景：按住空白处拖卡片，点一下（<6px）什么也不做。
        // 拖到窗口外就看不见了 —— 所以每次都夹在窗口里。
        MouseArea {
            id: monCardGrip
            objectName: "monCardGrip"
            anchors.fill: parent
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property point pressAt: Qt.point(0, 0)
            property real fromX: 0
            property real fromY: 0
            property bool moving: false
            onPressed: function (mouse) {
                pressAt = mapToItem(monDialog, mouse.x, mouse.y)
                fromX = monCard.x
                fromY = monCard.y
                moving = false
            }
            onPositionChanged: function (mouse) {
                if (!pressed)
                    return
                // 用窗口坐标算位移：卡片一动，mouse.x 也跟着变
                var at = mapToItem(monDialog, mouse.x, mouse.y)
                var dx = at.x - pressAt.x
                var dy = at.y - pressAt.y
                if (!moving && Math.sqrt(dx * dx + dy * dy) < 6)
                    return
                moving = true
                host.monCardX = Math.max(0, Math.min(
                    monDialog.width - monCard.width, fromX + dx))
                host.monCardY = Math.max(0, Math.min(
                    monDialog.height - monCard.height, fromY + dy))
            }
        }

        // ---- 抬头：缩略图 + 名字（就地改名）+ 关闭 ----
        Item {
            x: 10
            y: 8
            width: monCard.width - 20
            height: 36

            Rectangle {
                id: monIconBox
                objectName: "monIconBox"
                width: 34
                height: 34
                radius: 6
                color: host.paperLo
                clip: true
                Image {
                    objectName: "monEditIcon"
                    anchors.fill: parent
                    anchors.margins: 3
                    source: host.monIconUrl
                    visible: host.hasUrl(host.monIconUrl)
                    fillMode: Image.PreserveAspectFit
                    smooth: false
                }
                Text {
                    anchors.centerIn: parent
                    visible: !host.hasUrl(host.monIconUrl)
                    text: "?"
                    color: host.ink3
                    font.pixelSize: 13
                }
                // 用户："点击头像修改图标" —— 头像本身就是换图的按钮
                Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: host.paperLo
                    opacity: iconPickMouse.containsMouse ? 0.35 : 0
                    visible: iconPickMouse.containsMouse
                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: iconPickMouse.containsMouse
                    text: "换"
                    color: host.ink
                    font.family: host.uiFont
                    font.pixelSize: 10
                }
                MouseArea {
                    id: iconPickMouse
                    objectName: "monIconPick"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.openIconPicker()
                }
            }

            Rectangle {
                id: nameBox
                anchors.left: monIconBox.right
                anchors.leftMargin: 8
                anchors.right: monClose.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                height: 28
                radius: 6
                color: headerName.activeFocus ? host.paperLo : "transparent"
                border.width: 1
                border.color: headerName.activeFocus ? host.amber
                                                     : host.hairline
                Behavior on border.color {
                    ColorAnimation { duration: 120 }
                }
                TextField {
                    id: headerName
                    objectName: "monNameField"
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    verticalAlignment: TextInput.AlignVCenter
                    background: null
                    padding: 0
                    leftPadding: 2
                    rightPadding: 2
                    topPadding: 0
                    bottomPadding: 0
                    color: host.ink
                    font.family: host.uiFont
                    font.pixelSize: 14
                    font.bold: true
                    selectByMouse: true
                }
            }

            Item {
                id: monClose
                objectName: "monClose"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 16
                height: 16
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: monCloseMouse.containsMouse ? host.danger : host.ink3
                    font.pixelSize: 11
                }
                MouseArea {
                    id: monCloseMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.closeMonster()
                }
            }
        }

        Flickable {
            id: monFlick
            x: 10
            y: 50
            width: monCard.width - 20
            height: Math.min(monCol.implicitHeight, monCard.bodyMax)
            contentWidth: width
            contentHeight: monCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: monCol
                width: monFlick.width
                spacing: 6

                component Labeled: Item {
                    id: fieldRow
                    property string label: ""
                    property alias field: inner
                    width: 140
                    height: 24
                    Text {
                        width: 28
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: fieldRow.label
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 9
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.leftMargin: 30
                        anchors.right: parent.right
                        height: 22
                        radius: 5
                        anchors.verticalCenter: parent.verticalCenter
                        color: inner.activeFocus ? host.paperLo : "transparent"
                        border.width: 1
                        border.color: inner.activeFocus ? host.amber
                                                        : host.hairline
                        Behavior on border.color {
                            ColorAnimation { duration: 120 }
                        }
                        TextField {
                            id: inner
                            // 测试要按名字抓：Labeled 的 objectName + "Field"
                            objectName: fieldRow.objectName + "Field"
                            anchors.fill: parent
                            anchors.leftMargin: 5
                            anchors.rightMargin: 5
                            verticalAlignment: TextInput.AlignVCenter
                            background: null
                            padding: 0
                            leftPadding: 2
                            rightPadding: 2
                            topPadding: 0
                            bottomPadding: 0
                            horizontalAlignment: TextInput.AlignLeft
                            color: host.ink
                            font.family: host.monoFont
                            font.pixelSize: 11
                            selectByMouse: true
                        }
                    }
                }

                // ---- 数值：生命/攻击/防御一行，金币/经验一行 ----
                Row {
                    width: monCol.width
                    spacing: 8
                    Labeled {
                        id: fldHp
                        objectName: "monHp"
                        label: "生命"
                        width: (monCol.width - 16) / 3
                    }
                    Labeled {
                        id: fldAtk
                        objectName: "monAtk"
                        label: "攻击"
                        width: (monCol.width - 16) / 3
                    }
                    Labeled {
                        id: fldDef
                        objectName: "monDef"
                        label: "防御"
                        width: (monCol.width - 16) / 3
                    }
                }
                Row {
                    width: monCol.width
                    spacing: 10
                    Labeled {
                        id: fldGold
                        objectName: "monGold"
                        label: "金币"
                        width: (monCol.width - 10) / 2
                    }
                    Labeled {
                        id: fldExp
                        objectName: "monExp"
                        label: "经验"
                        width: (monCol.width - 10) / 2
                    }
                }

                Item { width: monCol.width; height: 2 }

                // ---- 技能：名称 / 数值 两列；加技能只有一个下拉按钮 ----
                Item {
                    width: monCol.width
                    height: 20
                    Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "技能"
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 10
                        font.letterSpacing: 2
                    }
                    FlatBtn {
                        id: skillBtn
                        objectName: "monSkillPick"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        label: "＋ 加技能"
                        onClicked: host.openSkillMenu()
                    }
                }

                // 技能行：一件技能两种长相 —— 用户："只有一行的和有多行的
                // 要有不同的显示方式，不然看起来太丑了"。
                //  · 单行（手册里查得到、没有参数、介绍一行放得下）：
                //    名称 | 介绍（一行，超出省略）| ✕，挤在 26 高的一行里；
                //  · 多行（有参数 / 介绍一行放不下 / 自定义要能写介绍）：
                //    整块浅底，名称一行、介绍占满整行折行、参数再往下排。
                Repeater {
                    model: host.monSkills
                    delegate: Rectangle {
                        id: skillRowItem
                        objectName: "monSkillRow"
                        width: monCol.width
                        readonly property int nameW: 78
                        readonly property int delW: 18
                        readonly property int gap: 5
                        readonly property int pad: 8
                        readonly property int inner: width - pad * 2
                        readonly property real singleEffectW:
                            width - nameW - delW - 2 * gap
                        // 委托里拿不到"这一行的下标"作为属性：一定要自己存一份
                        readonly property int skillIndex: index
                        readonly property var params:
                            modelData ? (modelData.params || {}) : ({})
                        readonly property bool custom:
                            !!(modelData && modelData.custom)
                        readonly property var schema:
                            modelData ? (modelData.schema || []) : []
                        readonly property string effectText:
                            modelData ? String(modelData.effect || "") : ""
                        // 介绍按同样字号量一遍：单行那点宽度放不下就换成多行块
                        readonly property bool multi: custom
                            || schema.length > 0
                            || effectMetrics.advanceWidth > singleEffectW
                        TextMetrics {
                            id: effectMetrics
                            font.family: host.uiFont
                            font.pixelSize: 9
                            text: skillRowItem.effectText
                        }
                        radius: 6
                        color: skillRowItem.multi ? host.paperLo : "transparent"
                        height: skillRowItem.multi
                                ? block.y + block.implicitHeight + skillRowItem.pad
                                : 26

                        // 名称：手册里的技能是只读（用户："除了自定义其余
                        // 技能名称都不能修改"），自定义那行才能改
                        Rectangle {
                            x: skillRowItem.multi ? skillRowItem.pad : 0
                            y: skillRowItem.multi ? 6 : 2
                            width: skillRowItem.multi
                                   ? skillRowItem.inner - skillRowItem.delW - 4
                                   : skillRowItem.nameW
                            height: 22
                            radius: 5
                            color: skillRowItem.custom ? host.paperHi
                                                       : "transparent"
                            border.width: skillRowItem.custom ? 1 : 0
                            border.color: skillNameField.activeFocus
                                          ? host.amber : host.hairline
                            Behavior on border.color {
                                ColorAnimation { duration: 120 }
                            }
                            TextField {
                                id: skillNameField
                                objectName: "monSkillName"
                                anchors.fill: parent
                                anchors.leftMargin: 4
                                anchors.rightMargin: 4
                                verticalAlignment: TextInput.AlignVCenter
                                background: null
                                padding: 0
                                leftPadding: 2
                                rightPadding: 2
                                topPadding: 0
                                bottomPadding: 0
                                readOnly: !skillRowItem.custom
                                color: host.ink
                                font.family: host.uiFont
                                font.pixelSize: 10
                                selectByMouse: true
                                text: modelData ? modelData.name : ""
                                onEditingFinished: host.setSkill(
                                    index, "name", text)
                            }
                        }

                        // 介绍 + 参数：单行模式挤在名称右边，多行模式整行铺开
                        Column {
                            id: block
                            x: skillRowItem.multi
                               ? skillRowItem.pad
                               : skillRowItem.nameW + skillRowItem.gap
                            y: skillRowItem.multi ? 32 : 0
                            width: skillRowItem.multi ? skillRowItem.inner
                                                      : skillRowItem.singleEffectW
                            spacing: 4

                            // 手册上的介绍（只读，数字不写进这句话里）；
                            // 手册里查不到的那种就写一句提示（灰的）
                            Text {
                                objectName: "monSkillEffect"
                                width: block.width
                                text: skillRowItem.effectText !== ""
                                      ? skillRowItem.effectText
                                      : "手册里查不到这个技能的说明"
                                visible: !skillRowItem.custom
                                wrapMode: Text.Wrap
                                // 单行模式：一行，长了省略；多行模式：不限行数
                                maximumLineCount: skillRowItem.multi ? 999 : 1
                                elide: Text.ElideRight
                                height: skillRowItem.multi
                                        ? implicitHeight : 26
                                verticalAlignment: skillRowItem.multi
                                                   ? Text.AlignTop
                                                   : Text.AlignVCenter
                                color: skillRowItem.effectText !== ""
                                       ? host.ink2 : host.ink3
                                font.family: host.uiFont
                                font.pixelSize: 9
                                lineHeight: 1.1
                            }
                            // 自定义技能：介绍是自己写的，能改（用户："自定义
                            // 怎么只能写技能名称不能写技能介绍"）
                            TextArea {
                                id: skillEffectField
                                objectName: "monSkillEffectEdit"
                                visible: skillRowItem.custom
                                width: block.width
                                height: Math.max(24, contentHeight + 8)
                                padding: 0
                                leftPadding: 5
                                rightPadding: 5
                                topPadding: 3
                                bottomPadding: 3
                                background: Rectangle {
                                    color: host.paperHi
                                    radius: 4
                                    border.width: 1
                                    border.color: skillEffectField.activeFocus
                                                  ? host.amber : host.hairline
                                }
                                wrapMode: TextArea.Wrap
                                placeholderText: "写这个技能的介绍（可不填）"
                                color: host.ink2
                                font.family: host.uiFont
                                font.pixelSize: 9
                                selectByMouse: true
                                text: skillRowItem.effectText
                                // 边打边记（和参数格一样，不重画，免得丢焦点）
                                onTextChanged: host.setSkill(
                                    index, "effect", text)
                            }

                            Flow {
                                objectName: "monSkillParams"
                                visible: skillRowItem.schema.length > 0
                                width: block.width
                                spacing: 8
                                Repeater {
                                    model: modelData ? (modelData.schema || []) : []
                                    delegate: Row {
                                        id: paramCell
                                        height: 18
                                        spacing: 3
                                        readonly property string field:
                                            String(modelData.field || "")
                                        readonly property string kind:
                                            String(modelData.type || "int")
                                        readonly property var current:
                                            skillRowItem.params[field]

                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: String(modelData.label || "")
                                            color: host.ink3
                                            font.family: host.uiFont
                                            font.pixelSize: 8
                                        }

                                        // 数字
                                        Rectangle {
                                            visible: paramCell.kind !== "toggle"
                                                     && paramCell.kind !== "choice"
                                            width: 34
                                            height: 18
                                            radius: 4
                                            color: host.paperLo
                                            border.width: 1
                                            border.color: paramField.activeFocus
                                                          ? host.amber : host.hairline
                                            TextField {
                                                id: paramField
                                                objectName: "monSkillParam"
                                                anchors.fill: parent
                                                anchors.leftMargin: 3
                                                anchors.rightMargin: 3
                                                verticalAlignment: TextInput.AlignVCenter
                                                horizontalAlignment: TextInput.AlignRight
                                                background: null
                                                padding: 0
                                                leftPadding: 1
                                                rightPadding: 1
                                                topPadding: 0
                                                bottomPadding: 0
                                                selectByMouse: true
                                                color: host.ink
                                                font.family: host.monoFont
                                                font.pixelSize: 9
                                                text: paramCell.current === undefined
                                                      || paramCell.current === null
                                                      ? ""
                                                      : String(paramCell.current)
                                                // 边打边记：原地改，不重画（不然丢焦点）
                                                onTextChanged: host.setSkillParam(
                                                    skillRowItem.skillIndex,
                                                    paramCell.field, text)
                                            }
                                        }
                                        Text {
                                            visible: paramCell.kind !== "toggle"
                                                     && paramCell.kind !== "choice"
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: String(modelData.unit || "")
                                            color: host.ink3
                                            font.family: host.uiFont
                                            font.pixelSize: 8
                                        }

                                        // 开关
                                        Rectangle {
                                            visible: paramCell.kind === "toggle"
                                            width: 18
                                            height: 18
                                            radius: 4
                                            color: paramCell.current
                                                   ? host.amber : host.paperLo
                                            border.width: 1
                                            border.color: paramCell.current
                                                          ? host.amber : host.hairline
                                            Text {
                                                anchors.centerIn: parent
                                                visible: !!paramCell.current
                                                text: "✓"
                                                color: host.paperHi
                                                font.pixelSize: 9
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: host.setSkillFlag(
                                                    skillRowItem.skillIndex,
                                                    paramCell.field,
                                                    !paramCell.current)
                                            }
                                        }

                                        // 二选一（十字 / 九宫格）
                                        Row {
                                            visible: paramCell.kind === "choice"
                                            spacing: 2
                                            Repeater {
                                                model: ["十字", "九宫格"]
                                                delegate: Rectangle {
                                                    width: 34
                                                    height: 18
                                                    radius: 4
                                                    color: paramCell.current === modelData
                                                           ? host.amber : host.paperLo
                                                    border.width: 1
                                                    border.color: paramCell.current === modelData
                                                                  ? host.amber : host.hairline
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: modelData
                                                        color: paramCell.current === modelData
                                                               ? host.paperHi : host.ink3
                                                        font.family: host.uiFont
                                                        font.pixelSize: 8
                                                    }
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: host.setSkillFlag(
                                                            skillRowItem.skillIndex,
                                                            paramCell.field,
                                                            modelData)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            // 多行块里 ✕ 贴块的右上角（和名称同一行）
                            x: skillRowItem.width - skillRowItem.delW
                               - (skillRowItem.multi ? skillRowItem.pad : 0)
                            y: skillRowItem.multi ? 8 : 4
                            width: skillRowItem.delW
                            height: 18
                            horizontalAlignment: Text.AlignHCenter
                            text: "✕"
                            color: skillDelMouse.containsMouse
                                   ? host.danger : host.ink3
                            font.pixelSize: 10
                            MouseArea {
                                id: skillDelMouse
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: host.removeSkill(index)
                            }
                        }
                    }
                }

                Text {
                    width: monCol.width
                    height: 16
                    visible: host.monSkills.length === 0
                    text: "还没有技能，点「＋ 加技能」从下拉里选。"
                    color: host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 9
                    verticalAlignment: Text.AlignVCenter
                }

                Item { width: monCol.width; height: 2 }
            }
        }

        // ---- 底部：删除 / 取消 / 保存 ----
        Row {
            x: 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            width: monCard.width - 20
            spacing: 6
            FlatBtn {
                objectName: "monDelete"
                danger: true
                label: "删除这只"
                onClicked: host.deleteMonster()
            }
            Item {
                width: Math.max(0, parent.width - 88 - 46 - 46 - 12)
                height: 1
            }
            FlatBtn {
                objectName: "monCancel"
                label: "取消"
                onClicked: host.closeMonster()
            }
            FlatBtn {
                objectName: "monSave"
                solid: true
                label: "保存"
                onClicked: commit()
                }
            }
    }
}
