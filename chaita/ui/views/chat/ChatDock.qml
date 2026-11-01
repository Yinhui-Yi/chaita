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

    // 收起着的时候来了新消息，标题行上亮一个小蓝点：数一数"看过几条"
    readonly property int count: host.chats ? host.chats.length : 0
    property int seenCount: 0
    readonly property bool unread: host.chatCollapsed && dock.count > dock.seenCount
    onCountChanged: if (!host.chatCollapsed) dock.seenCount = dock.count
    Component.onCompleted: dock.seenCount = dock.count
    Connections {
        target: host
        function onChatCollapsedChanged() {
            if (!host.chatCollapsed)
                dock.seenCount = dock.count
        }
    }

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

    // 标题行：点一下收起 / 展开整块对话（收起后只剩这一行）
    Item {
        id: head
        objectName: "chatHead"
        x: 0
        y: 0
        width: parent.width
        height: host.chatHeadH

        Text {
            objectName: "chatChevron"
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            width: 12
            text: host.chatCollapsed ? "▸" : "▾"
            color: headMouse.containsMouse ? Theme.amber : Theme.ink3
            font.pixelSize: 10
        }
        Text {
            id: headLabel
            x: 26
            anchors.verticalCenter: parent.verticalCenter
            text: "对话"
            color: Theme.ink
            font.family: Theme.uiFont
            font.pixelSize: 12
            font.bold: true
        }
        // 收起着时来了新消息：一颗小蓝点
        Rectangle {
            objectName: "chatUnreadDot"
            visible: dock.unread
            anchors.left: headLabel.right
            anchors.leftMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            width: 7
            height: 7
            radius: 3.5
            color: Theme.amber
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: dock.count > 0 ? dock.count + " 条" : ""
            color: Theme.ink3
            font.family: Theme.monoFont
            font.pixelSize: 10
        }
        MouseArea {
            id: headMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: controller.setChatCollapsed(!host.chatCollapsed)
        }
    }

    // 对话内容：会折行、可能比一屏长，所以放在一个会自己滚到底的小窗里
    Flickable {
        id: chatFlick
        objectName: "chatFlick"
        x: 12
        y: host.chatHeadH + 8
        width: parent.width - 24
        height: host.chatLogH
        contentWidth: width
        contentHeight: chatCol.implicitHeight
        clip: true
        visible: host.chatLogH > 0 && !host.chatCollapsed
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
        visible: host.chatLogH > 0 && !host.chatCollapsed
    }

    // 输入栏
    Item {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: host.chatBarH
        visible: !host.chatCollapsed

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

            // 发送：框里右边的小圆按钮，画一只纸飞机（矢量，不用字体字符）。
            // 框里没字时是灰的、点了不发；有字才变蓝，让"能不能发"一眼看得出
            Rectangle {
                id: sendBtn
                objectName: "chatSend"
                readonly property bool ready: chatInput.text.trim() !== ""
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                height: 24
                radius: 12
                color: !sendBtn.ready ? Theme.hover
                     : (sendMouse.pressed ? Theme.amberPress
                        : (sendMouse.containsMouse ? Theme.amberHover : Theme.amber))
                Behavior on color { ColorAnimation { duration: 100 } }

                Canvas {
                    id: plane
                    anchors.centerIn: parent
                    width: 14
                    height: 14
                    property color ink: sendBtn.ready ? Theme.amberInk : Theme.ink3
                    onInkChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        // 24×24 的纸飞机轮廓缩到 14×14
                        var k = width / 24
                        ctx.fillStyle = plane.ink
                        ctx.beginPath()
                        ctx.moveTo(3 * k, 11 * k)
                        ctx.lineTo(21 * k, 3 * k)
                        ctx.lineTo(13 * k, 21 * k)
                        ctx.lineTo(10.5 * k, 13.5 * k)
                        ctx.closePath()
                        ctx.fill()
                    }
                }
                MouseArea {
                    id: sendMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: sendBtn.ready ? Qt.PointingHandCursor : Qt.ArrowCursor
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
