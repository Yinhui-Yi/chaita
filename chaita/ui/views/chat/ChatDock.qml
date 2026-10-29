import QtQuick
import QtQuick.Controls.Basic

// 底部对话：问答历史（会折行、会滚到最新）+ 输入框 + 发送。
//
// 主窗口的一块（不是覆盖层），一个界面一个文件夹。
// 这里管自己的滚动和发送；对话记录本身在 host 上（`host.chats`，由 controller
// 的 chatLog 推过来），`chatLines()` 也在主窗口（`sync()` 还要用）。
Rectangle {
    id: dock

    // 归属：主窗口（对话记录和状态都在它身上）
    property var host

    // 对话区现在有多高（主窗口算 dockH 要用：聊得越多窗口越高，最多 180）
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
    radius: 8
    color: host.paperHi
    border.width: 1
    border.color: host.hairline
    visible: !host.collapsed

    // 对话内容：会折行、可能比一屏长，所以放在一个会自己滚到底的小窗里
    Flickable {
        id: chatFlick
        objectName: "chatFlick"
        x: 10
        y: 8
        width: parent.width - 20
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
            spacing: 3

            Repeater {
                model: host.chats
                // 一行一条：谁说 + 内容（折行）+ 时间。
                // 内容不再 elide：超出的话换行往下长，行高跟着文字走。
                delegate: Item {
                    objectName: "chatRowItem"
                    width: chatCol.width
                    height: Math.max(12, chatSay.implicitHeight)

                    Text {
                        objectName: "chatWho"
                        x: 0
                        y: 0
                        width: 22
                        text: modelData && modelData.who ? modelData.who : ""
                        color: host.ink3
                        font.family: host.uiFont
                        font.pixelSize: 9
                        elide: Text.ElideRight
                    }
                    Text {
                        id: chatSay
                        objectName: "chatText"
                        x: 28
                        y: 0
                        width: parent.width - 28 - 28
                        text: modelData && modelData.text ? modelData.text : ""
                        color: modelData && modelData.who === "你"
                               ? host.ink : host.ink2
                        font.family: host.uiFont
                        font.pixelSize: 9
                        lineHeight: 1.15
                        wrapMode: Text.Wrap
                    }
                    Text {
                        objectName: "chatAt"
                        x: parent.width - 26
                        y: 0
                        width: 26
                        text: modelData && modelData.at ? modelData.at : ""
                        color: host.ink3
                        font.family: host.monoFont
                        font.pixelSize: 8
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }

    Item {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        anchors.bottomMargin: 7
        height: 26

        Rectangle {
            id: sendBtn
            objectName: "chatSend"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 26
            height: 26
            radius: 8
            color: sendMouse.containsMouse ? "#A6771F" : host.amber
            Behavior on color { ColorAnimation { duration: 120 } }
            Text {
                anchors.centerIn: parent
                text: "↑"
                color: host.amberInk
                font.pixelSize: 12
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

        Rectangle {
            objectName: "inputPill"
            anchors.left: parent.left
            anchors.right: sendBtn.left
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            height: 26
            radius: 8
            color: host.paperLo
            border.width: 1
            border.color: chatInput.activeFocus ? host.amber : "#E0D7C6"
            Behavior on border.color { ColorAnimation { duration: 120 } }

            TextInput {
                id: chatInput
                objectName: "chatInput"
                anchors.fill: parent
                anchors.leftMargin: 9
                anchors.rightMargin: 8
                verticalAlignment: TextInput.AlignVCenter
                color: host.ink
                font.family: host.uiFont
                font.pixelSize: 10
                selectByMouse: true
                clip: true
                onAccepted: dock.sendChat()
            }
            // 没有 placeholder：用户说"默认提示真low"，空着就空着
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