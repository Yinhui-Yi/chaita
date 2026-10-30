import QtQuick
import QtQuick.Controls.Basic
import "../../shared"

// 改参数卡片（路线链版）：点链上那个缩略图，改这一格怪的血攻防 / 资源的效果 / 技能参数。
//
// 和伤害计算的改参数卡片是**同一个长相**（用户："怎么和伤害计算不一样"、"用你的狗眼
// 好好看看"）：字段一样、底部也一样（「删掉这步」+「完成」）。换这一格是什么不在这张
// 卡片里 —— 点链上的**箭头**（和伤害计算点箭头同一个分工）。
// 路线链窗口的覆盖层（z=30），放在它自己的文件夹里。
Item {
    id: routeEditPanel

    // 归属：主窗口（状态都在它身上）
    property var host
    property var ctx: ({})
    objectName: "routeEditLayer"
    anchors.fill: parent
    visible: ctx.editLayer
    z: 30

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Qt.rgba(0.11, 0.10, 0.08, 0.32)
        MouseArea {
            anchors.fill: parent
            onClicked: host.routeEditDone(ctx)
        }
    }

    Rectangle {
        id: routeEditCard
        objectName: "routeEditCard"
        anchors.centerIn: parent
        width: parent.width - 20
        height: Math.min(parent.height - 20,
                         40 + routeEditCol.implicitHeight + 34)
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
            text: "改参数：" + String((ctx.editData || {}).name || "")
            color: host.ink
            font.family: host.uiFont
            font.pixelSize: 11
            font.bold: true
            elide: Text.ElideRight
        }

        Flickable {
            x: 8
            y: 26
            width: routeEditCard.width - 16
            height: Math.min(routeEditCol.implicitHeight,
                             routeEditCard.height - 60)
            contentWidth: width
            contentHeight: routeEditCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: routeEditCol
                width: parent.width
                spacing: 4

                // 数量（和伤害计算同一个长相：一格里的怪/资源有几个）
                Row {
                    width: routeEditCol.width
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
                        width: 40
                        height: 22
                        radius: 5
                        color: host.paperLo
                        border.width: 1
                        border.color: countField.activeFocus
                                      ? host.amber : host.hairline
                        TextField {
                            id: countField
                            objectName: "routeEditCount"
                            anchors.fill: parent
                            horizontalAlignment: TextInput.AlignHCenter
                            verticalAlignment: TextInput.AlignVCenter
                            background: null
                            color: host.ink
                            font.family: host.monoFont
                            font.pixelSize: 10
                            selectByMouse: true
                            text: String(Number((ctx.editData || {}).count || 1))
                            onTextChanged: {
                                var clean = String(text).replace(/[^0-9]/g, "")
                                if (clean !== String(text)) {
                                    text = clean
                                    return
                                }
                                var now = clean === "" ? 1 : Number(clean)
                                if (now !== Number((ctx.editData || {}).count || 1))
                                    host.routeEditSet(ctx, "count", clean)
                            }
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: (ctx.editData || {}).kind === "item"
                              ? "个" : "只（同样的一只只算）"
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 8
                    }
                }

                // 怪：血量 / 攻击 / 防御
                Row {
                    width: routeEditCol.width
                    spacing: 6
                    visible: (ctx.editData || {}).kind !== "item"
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
                                    objectName: "routeEdit" + modelData[0]
                                    anchors.fill: parent
                                    anchors.leftMargin: 3
                                    anchors.rightMargin: 3
                                    verticalAlignment: TextInput.AlignVCenter
                                    background: null
                                    color: host.ink
                                    font.family: host.monoFont
                                    font.pixelSize: 9
                                    selectByMouse: true
                                    text: String(Number((ctx.editData || {})[modelData[0]] || 0))
                                    onTextChanged: {
                                        var clean = String(text).replace(/[^0-9]/g, "")
                                        if (clean !== String(text)) {
                                            text = clean
                                            return
                                        }
                                        var now = clean === "" ? 0 : Number(clean)
                                        if (now !== Number((ctx.editData || {})[modelData[0]] || 0))
                                            host.routeEditSet(ctx, modelData[0], clean)
                                    }
                                }
                            }
                        }
                    }
                }

                // 资源：效果 —— 一段一条「属性 + 加减号 + 数字框」（和伤害计算同一个控件）
                Row {
                    width: routeEditCol.width
                    spacing: 6
                    visible: (ctx.editData || {}).kind === "item"
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
                        id: routeEffectEditor
                        width: parent.width - 54 - 6
                        fieldName: "routeEditEffect"
                        parts: controller
                               ? controller.itemEffectPartList(
                                      (ctx.editData || {}).effect || "")
                               : []
                        onPartChanged: function (partIndex, value) {
                            host.routeEditSet(ctx, "effect",
                                controller.itemEffectWithPart(
                                    (ctx.editData || {}).effect || "",
                                    partIndex, value))
                        }
                    }
                }

                // 技能参数（破甲的防御百分比、反击的攻击百分比……）
                Repeater {
                    model: ctx.editParams
                    delegate: Row {
                        width: routeEditCol.width
                        spacing: 4
                        Text {
                            width: Math.max(80, routeEditCol.width - 130)
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
                                objectName: "routeEditParam"
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
                                        host.routeEditSkill(ctx, 
                                            modelData.skillIndex,
                                            modelData.field, clean)
                                }
                            }
                        }
                        // 开关类参数（"伤害加到自身"）
                        Rectangle {
                            objectName: "routeEditToggle"
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
                                onClicked: host.routeEditSkill(ctx, 
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
                                        onClicked: host.routeEditSkill(ctx, 
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
                    width: routeEditCol.width
                    visible: ((ctx.editData || {}).skills || []).length > 0
                    text: "技能参数就按怪物编辑里填的那份算（改这里只影响这条路线）"
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
            objectName: "routeEditDelete"
            danger: true
            label: "删掉这步"
            onClicked: host.routeEditRemove(ctx)
        }
        Item {
            width: Math.max(0, routeEditCard.width - 20 - 74 - 46 - 12)
            height: 1
        }
        FlatBtn {
            objectName: "routeEditDone"
            solid: true
            label: "完成"
            onClicked: host.routeEditDone(ctx)
        }
    }
    }
}
