import QtQuick
import "."

// 图标按钮：一个字形（↻ ⚔ ✕ 这类），平时无底，悬停才出浅灰底。
// 导航条上的工具按钮都用它（原来每个按钮各写一份 Item + Text + MouseArea）。
Rectangle {
    id: btn

    property string glyph: ""
    property int glyphSize: 13
    // 悬停时字的颜色（默认强调蓝；关闭键传 Theme.danger）
    property color hoverInk: Theme.amber
    // 悬停时的底（默认浅灰；关闭键传 Theme.dangerSoft）
    property color hoverBack: Theme.hover
    // 常亮（比如"正在刷新"）：字用次要色
    property bool dim: false
    signal clicked()

    width: Theme.controlH
    height: Theme.controlH
    radius: Theme.radius
    color: mouse.containsMouse ? btn.hoverBack : "transparent"
    Behavior on color { ColorAnimation { duration: 100 } }

    Text {
        anchors.centerIn: parent
        text: btn.glyph
        color: mouse.containsMouse ? btn.hoverInk
             : (btn.dim ? Theme.ink3 : Theme.ink2)
        font.pixelSize: btn.glyphSize
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }
}
