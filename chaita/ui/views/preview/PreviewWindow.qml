import QtQuick
import QtQuick.Window
import "../shared"

// 点缩略图看大图（用户 2026-10-31："我现在点队列里的缩略图怎么不放大"）。
//
// 无边框 + 置顶 + Qt.Tool，和其它窗口同一个长相；**点一下或按 Esc 就关**。
// 铁律：**任何显示路径都不许放大** —— 图多大就摆多大，只有比屏幕/上限还大才缩。
Window {
    id: previewWindow
    objectName: "previewWindow"

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    visible: false
    title: "看图"

    property var host
    // 要看的那张图（file:// URL）
    property string source: ""
    // 上限：再大就缩，绝不放大
    readonly property int maxSide: 900

    function fitToImage() {
        var realWidth = Number(shot.sourceSize.width)
        var realHeight = Number(shot.sourceSize.height)
        if (!(realWidth > 0 && realHeight > 0))
            return
        var scale = Math.min(1, previewWindow.maxSide / realWidth,
                             previewWindow.maxSide / realHeight)
        previewWindow.width = Math.max(120, Math.round(realWidth * scale)) + 10
        previewWindow.height = Math.max(90, Math.round(realHeight * scale)) + 10
        previewWindow.place()
    }

    // 摆在屏幕中间
    function place() {
        var area = previewWindow.screen || ({})
        var screenWidth = Number(area.width || 0)
        var screenHeight = Number(area.height || 0)
        if (!(screenWidth > 0 && screenHeight > 0))
            return
        previewWindow.x = Math.max(0, Math.round((screenWidth - width) / 2))
        previewWindow.y = Math.max(0, Math.round((screenHeight - height) / 2))
    }

    // 关掉了（宿主拿它把引用清掉，下次再看重新建）
    // 注意别叫 `closing`：Window 自带一个同名信号，重名会报
    // "Duplicate signal name: invalid override of property change signal"
    signal dismissed()

    onDismissed: visible = false

    function open(url) {
        var text = String(url || "")
        if (text === "")
            return false
        previewWindow.source = text
        previewWindow.visible = true
        previewWindow.fitToImage()
        previewWindow.raise()
        previewWindow.requestActivate()
        return true
    }

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: Theme.paperHi
        border.width: 1
        border.color: Theme.edge
        clip: true

        Image {
            id: shot
            objectName: "previewImage"
            anchors.fill: parent
            anchors.margins: 5
            source: previewWindow.source
            fillMode: Image.PreserveAspectFit
            // 素材库那套一律不插值放大，看着才是原样
            smooth: false
            asynchronous: true
            onStatusChanged: previewWindow.fitToImage()
        }
    }

    // 点一下就关（整窗都是热区）
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: previewWindow.dismissed()
    }

    Shortcut {
        sequences: ["Esc", "Return"]
        onActivated: previewWindow.dismissed()
    }
}
