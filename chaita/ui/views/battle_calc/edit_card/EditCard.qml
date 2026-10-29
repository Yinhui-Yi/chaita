import QtQuick
import QtQuick.Controls.Basic
import "../../shared"

// 改参数卡片：点链上那个缩略图，改数量 / 怪的血攻防 / 资源的效果 / 技能参数。
//
// 伤害计算窗口的覆盖层（z=30），所以放在它自己的文件夹里
// （一层 UI 一个文件夹）。状态在主窗口上（`host.battleEditData` /
// `host.battleEditParams` / `host.battleEditPlan`），这里只画和改。
    Item {
id: battleEditPanel

    // 归属：主窗口（状态都在它身上）
    property var host
objectName: "battleEditLayer"
anchors.fill: parent
visible: host.battleEditLayer
z: 30

Rectangle {
    anchors.fill: parent
    radius: 8
    color: Qt.rgba(0.11, 0.10, 0.08, 0.32)
    MouseArea {
        anchors.fill: parent
        onClicked: host.battleEditLayer = false
    }
}

Rectangle {
    id: battleEditCard
    objectName: "battleEditCard"
    anchors.centerIn: parent
    width: parent.width - 20
    height: Math.min(parent.height - 20,
                     40 + battleEditCol.implicitHeight + 34)
    radius: 8
    color: host.paperHi
    border.width: 1
    border.color: host.edge
    clip: true
    MouseArea { anchors.fill: parent }

    Text {
        x: 10
        y: 6
        width: parent.width - 20
        text: "改参数：" + String((host.battleEditData || {}).name || "")
        color: host.ink
        font.family: host.uiFont
        font.pixelSize: 11
        font.bold: true
        elide: Text.ElideRight
    }

    Flickable {
        x: 8
        y: 26
        width: battleEditCard.width - 16
        height: Math.min(battleEditCol.implicitHeight,
                         battleEditCard.height - 60)
        contentWidth: width
        contentHeight: battleEditCol.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: battleEditCol
            width: parent.width
            spacing: 4

            // 数量
            Row {
                width: battleEditCol.width
                spacing: 6
                Text {
                    width: 54
                    anchors.verticalCenter: parent.verticalCenter
                    text: "数量"
                    color: host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 9
                }
                Rectangle {
                    // 数量最多三位数：框就按数字的宽度来，不留一大截空白
                    // （用户："数量的文本框太长了"）
                    width: 40
                    height: 22
                    radius: 5
                    color: host.paperLo
                    border.width: 1
                    border.color: countField.activeFocus
                                  ? host.amber : host.hairline
                    TextField {
                        id: countField
                        objectName: "battleEditCount"
                        anchors.fill: parent
                        horizontalAlignment: TextInput.AlignHCenter
                        verticalAlignment: TextInput.AlignVCenter
                        background: null
                        color: host.ink
                        font.family: host.monoFont
                        font.pixelSize: 10
                        selectByMouse: true
                        text: String(Number((host.battleEditData || {}).count || 1))
                        onTextChanged: {
                            var clean = String(text).replace(/[^0-9]/g, "")
                            if (clean !== String(text)) {
                                text = clean
                                return
                            }
                            var now = clean === "" ? 1 : Number(clean)
                            if (now !== Number((host.battleEditData || {}).count || 1))
                                host.battleEditSet(
                                                  "count", clean)
                        }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: (host.battleEditData || {}).kind === "item"
                          ? "个" : "只（同样的一只只算）"
                    color: host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 8
                }
            }

            // 怪：血量 / 攻击 / 防御
            Row {
                width: battleEditCol.width
                spacing: 6
                visible: (host.battleEditData || {}).kind !== "item"
                Repeater {
                    model: [["hp", "血量"], ["atk", "攻击"],
                            ["def", "防御"]]
                    delegate: Row {
                        spacing: 4
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData[1]
                            color: host.ink3
                            font.family: host.uiFont
                            font.pixelSize: 8
                        }
                        Rectangle {
                            width: 76
                            height: 22
                            radius: 5
                            color: host.paperLo
                            border.width: 1
                            border.color: statField.activeFocus
                                          ? host.amber : host.hairline
                            TextField {
                                id: statField
                                objectName: "battleEdit" + modelData[0]
                                anchors.fill: parent
                                anchors.leftMargin: 3
                                anchors.rightMargin: 3
                                verticalAlignment: TextInput.AlignVCenter
                                background: null
                                color: host.ink
                                font.family: host.monoFont
                                font.pixelSize: 9
                                selectByMouse: true
                                text: String(Number((host.battleEditData || {})[modelData[0]] || 0))
                                onTextChanged: {
                                    var clean = String(text).replace(/[^0-9]/g, "")
                                    if (clean !== String(text)) {
                                        text = clean
                                        return
                                    }
                                    var now = clean === "" ? 0 : Number(clean)
                                    if (now !== Number((host.battleEditData || {})[modelData[0]] || 0))
                                        host.battleEditSet(
                                                          modelData[0], clean)
                                }
                            }
                        }
                    }
                }
            }

            // 资源：效果 —— 一段一条「属性 + 加减号 + 数字框」，属性写死、数值能改
            // （用户："怎么伤害计算界面的宝石的攻击力不是写死的？"、
            //  "黄宝石每个值都要能改"）。和「这一层」资源行用的是**同一个控件**
            // （shared/EffectEditor.qml），拼回去的规则在 iteminfo 一处。
            Row {
                width: battleEditCol.width
                spacing: 6
                visible: (host.battleEditData || {}).kind === "item"
                Text {
                    width: 54
                    height: 20
                    verticalAlignment: Text.AlignVCenter
                    text: "效果"
                    color: host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 9
                }
                EffectEditor {
                    id: battleEffectEditor
                    width: parent.width - 54 - 6
                    fieldName: "battleEditEffect"
                    // controller 在窗口销毁阶段会是 null，绑一次空列表兜住
                    parts: controller
                           ? controller.itemEffectPartList(
                                 (host.battleEditData || {}).effect || "")
                           : []
                    onPartChanged: function (partIndex, value) {
                        host.battleEditSet("effect",
                            controller.itemEffectWithPart(
                                (host.battleEditData || {}).effect || "",
                                partIndex, value))
                    }
                }
            }

            // 技能参数（破甲的防御百分比、反击的攻击百分比……）
            Repeater {
                model: host.battleEditParams
                delegate: Row {
                    width: battleEditCol.width
                    spacing: 4
                    Text {
                        width: Math.max(80, battleEditCol.width - 130)
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.skillName + " · "
                              + modelData.label
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 8
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        width: 56
                        height: 20
                        radius: 5
                        visible: modelData.type !== "toggle"
                                 && modelData.type !== "choice"
                        color: host.paperLo
                        border.width: 1
                        border.color: paramField.activeFocus
                                      ? host.amber : host.hairline
                        TextField {
                            id: paramField
                            objectName: "battleEditParam"
                            anchors.fill: parent
                            horizontalAlignment: TextInput.AlignHCenter
                            verticalAlignment: TextInput.AlignVCenter
                            background: null
                            color: host.ink
                            font.family: host.monoFont
                            font.pixelSize: 9
                            selectByMouse: true
                            text: String(modelData.value)
                            onTextChanged: {
                                var clean = String(text)
                                    .replace(/[^0-9.]/g, "")
                                if (clean !== String(text)) {
                                    text = clean
                                    return
                                }
                                if (clean !== String(modelData.value))
                                    host.battleEditSkill(
                                        modelData.skillIndex,
                                        modelData.field, clean)
                            }
                        }
                    }
                    // 开关类参数（"伤害加到自身"）
                    Rectangle {
                        objectName: "battleEditToggle"
                        width: 20
                        height: 20
                        radius: 4
                        visible: modelData.type === "toggle"
                        readonly property bool on:
                            String(modelData.value) === "true"
                            || String(modelData.value) === "1"
                        color: on ? host.amber : host.paperLo
                        border.width: 1
                        border.color: on ? host.amber : host.hairline
                        Text {
                            anchors.centerIn: parent
                            visible: parent.on
                            text: "✓"
                            color: host.paperHi
                            font.pixelSize: 9
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: host.battleEditSkill(
                                modelData.skillIndex,
                                modelData.field,
                                parent.on ? "" : "true")
                        }
                    }
                    // 二选一（十字 / 九宫格）
                    Row {
                        id: choiceRow
                        visible: modelData.type === "choice"
                        spacing: 3
                        readonly property var param: modelData
                        Repeater {
                            model: ["十字", "九宫格"]
                            delegate: Rectangle {
                                width: 42
                                height: 20
                                radius: 4
                                readonly property bool on:
                                    String(modelData) === String(choiceRow.param.value)
                                color: on ? host.amber : host.paperLo
                                border.width: 1
                                border.color: on ? host.amber
                                                 : host.hairline
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData
                                    color: on ? host.paperHi
                                              : host.ink2
                                    font.family: host.uiFont
                                    font.pixelSize: 8
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: host.battleEditSkill(
                                        choiceRow.param.skillIndex,
                                        choiceRow.param.field,
                                        modelData)
                                }
                            }
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: String(modelData.unit || "")
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 8
                    }
                }
            }

            Text {
                width: battleEditCol.width
                visible: ((host.battleEditData || {}).skills || []).length > 0
                text: "技能参数就按怪物编辑里填的那份算（改这里只影响这次计算）"
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 8
                wrapMode: Text.Wrap
            }
        }
    }

    Row {
        x: 10
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 8
        spacing: 6
        FlatBtn {
            objectName: "battleEditDelete"
            danger: true
            label: "删掉这步"
            onClicked: {
                host.battleEditRemove()
                host.battleEditLayer = false
            }
        }
        Item {
            width: Math.max(0, battleEditCard.width - 20 - 74 - 46 - 12)
            height: 1
        }
        FlatBtn {
            objectName: "battleEditDone"
            solid: true
            label: "完成"
            onClicked: host.battleEditLayer = false
        }
    }
}
    }
