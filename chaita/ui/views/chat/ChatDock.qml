import QtQuick
import QtQuick.Controls.Basic
// 共用件（配色/卡片）在上一层
import "../shared"

// 底部对话：一块面，上面是气泡对话区（会折行、会滚到最新），下面是输入栏。
//
// 主窗口的一块（不是覆盖层），一个界面一个文件夹。
// 这里管自己的滚动和发送；对话记录本身在 host 上（`host.chats`，由 controller
// 的 chatLog 推过来）。
//
// 长相：你说的靠右、淡蓝底；AI 说的靠左、浅灰底；每条下面一行小字时间。
// 输入栏是一个圆角输入框，发送键是框里右边的小圆按钮 —— 不是外挂的方块。
// 没有对话时只剩输入栏，最矮。
Rectangle {
    id: dock

    // 归属：主窗口（对话记录和状态都在它身上）
    property var host

    // 对话区现在有多高（主窗口算 dockH 要用：聊得越多窗口越高，最多 chatLogMax）
    readonly property int logHeight: chatCol.implicitHeight

    // 输入框有没有焦点（Esc 先收别的层、别把窗口关了，靠它判断）
    readonly property bool inputFocused: chatInput.activeFocus

    objectName: "chatBar"
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.leftMargin: host.padH
    anchors.rightMargin: host.padH
    anchors.bottomMargin: host.padV
    height: host.dockH
    // 和上面的卡同一个长相：白底圆角 + 细外框 + 底沿一线暗边
    radius: 8
    color: Theme.paper
    border.width: 1
    border.color: Theme.cardEdge
    visible: !host.collapsed

    Rectangle {
        z: -1
        anchors.fill: parent
        anchors.topMargin: 2
        anchors.bottomMargin: -1
        radius: parent.radius
        color: Theme.cardShade
    }

    // 对话内容：会折行、可能比一屏长，所以放在一个会自己滚到底的小窗里
    Flickable {
        id: chatFlick
        objectName: "chatFlick"
        x: 12
        y: 8
        width: parent.width - 24
        height: host.chatLogH
        contentWidth: width
        contentHeight: chatCol.implicitHeight
        clip: true
        visible: host.chatLogH > 0
        boundsBehavior: Flickable.StopAtBounds
        // 新的那句在最下面：内容或可视高度变了都滚到底（看完整历史的最后一句）
        onContentHeightChanged: dock.scrollChatToEnd()
        onHeightChanged: dock.scrollChatToEnd()

        Column {
            id: chatCol
            width: chatFlick.width
            spacing: 8

            Repeater {
                model: host.chats
                // 一条一个气泡：靠右 = 你，靠左 = AI。内容会折行，气泡宽度跟着字走。
                delegate: Item {
                    id: msg
                    objectName: "chatRowItem"
                    readonly property bool mine: !!modelData && modelData.who === "你"
                    // 气泡最宽占 82%，再宽就折行
                    readonly property real maxTextW: msg.width * 0.82 - 24
                    width: chatCol.width
                    height: bubble.height

                    TextMetrics {
                        id: metrics
                        font.family: Theme.uiFont
                        font.pixelSize: 12
                        text: modelData && modelData.text ? modelData.text : ""
                    }

                    Rectangle {
                        id: bubble
                        x: msg.mine ? msg.width - width : 0
                        width: Math.max(say.width, stamp.implicitWidth) + 24
                        height: bubbleCol.implicitHeight + 12
                        radius: 10
                        color: msg.mine ? Theme.amberSoft : Theme.tile

                        Column {
                            id: bubbleCol
                            x: 12
                            y: 6
                            spacing: 0

                            Text {
                                id: say
                                objectName: "chatText"
                                width: Math.min(Math.ceil(metrics.advanceWidth) + 1,
                                                msg.maxTextW)
                                text: modelData && modelData.text ? modelData.text : ""
                                color: Theme.ink
                                font.family: Theme.uiFont
                                font.pixelSize: 12
                                lineHeight: 1.2
                                wrapMode: Text.Wrap
                            }
                            // 时间：一直显示，小字、靠气泡右下角
                            Text {
                                id: stamp
                                objectName: "chatAt"
                                width: Math.max(say.width, implicitWidth)
                                horizontalAlignment: Text.AlignRight
                                text: modelData && modelData.at ? modelData.at : ""
                                color: Theme.ink3
                                font.family: Theme.monoFont
                                font.pixelSize: 9
                            }
                        }
                    }
                }
            }
        }
    }

    // 对话区和输入栏之间一条细线（没有对话时不画）
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 1
        anchors.rightMargin: 1
        anchors.bottom: parent.bottom
        anchors.bottomMargin: host.chatBarH
        height: 1
        color: Theme.hairline
        visible: host.chatLogH > 0
    }

    // 输入栏
    Item {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: host.chatBarH

        // 圆角输入框；发送键在框里右边，所以字要给它让出位置
        Rectangle {
            objectName: "inputPill"
            anchors.fill: parent
            anchors.margins: 8
            radius: height / 2
            color: Theme.tile
            border.width: 1
            border.color: chatInput.activeFocus ? Theme.amber : "transparent"
            Behavior on border.color { ColorAnimation { duration: 100 } }

            TextInput {
                id: chatInput
                objectName: "chatInput"
                anchors.left: parent.left
                anchors.right: sendBtn.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.leftMargin: 14
                anchors.rightMargin: 6
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 12
                selectByMouse: true
                clip: true
                onAccepted: dock.sendChat()
            }
            // 没有 placeholder：用户说"默认提示真low"，空着就空着

            // 发送：框里右边的小圆按钮
            Rectangle {
                id: sendBtn
                objectName: "chatSend"
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                height: 24
                radius: 12
                color: sendMouse.pressed ? Theme.amberPress
                     : (sendMouse.containsMouse ? Theme.amberHover : Theme.amber)
                Behavior on color { ColorAnimation { duration: 100 } }
                Text {
                    anchors.centerIn: parent
                    text: "↑"
                    color: Theme.amberInk
                    font.pixelSize: 13
                    font.bold: true
                }
                MouseArea {
                    id: sendMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: dock.sendChat()
                }
            }
        }
    }

    // ---- 动作（发和滚都归这个文件，主窗口不再各留一份） ----

    // 新的那句在下面：把对话滚到底（内容没超出就什么都不用做）
    function scrollChatToEnd() {
        if (chatFlick.contentHeight <= chatFlick.height) return
        chatFlick.contentY = chatFlick.contentHeight - chatFlick.height
    }

    // 空的不发；发完清空输入框（回复由 controller 的 chatLog 推回来）
    function sendChat() {
        var text = chatInput.text
        if (!text || text.trim() === "") return
        controller.sendChat(text)
        chatInput.text = ""
    }
}
