import QtQuick
import "."

// 「读取」按钮：分区标题右边那颗实心强调色小按钮，地图栏和怪物栏各放一颗。
// 字永远写「读取」：手册分页，翻到下一页还得再点它；写成「读取中」会让人以为
// 不能再按（用户："要通过按读取中来开启第二页太反直觉"）。
// 正在读用右上角一颗呼吸的小点表示，按钮本身照样能点（可并行读取）。
Rectangle {
    id: btn

    // 归属：主窗口（runningCount / readMode 在它身上）
    property var host
    // 读什么："map" / "monsters"
    property string mode: ""
    // 小点的 objectName（测试和预览按名字找）
    property string busyName: ""
    readonly property int busy: host ? host.runningCount(btn.mode) : 0

    width: 48
    height: 22
    radius: Theme.radius
    color: mouse.pressed ? Theme.accentPress
         : (mouse.containsMouse ? Theme.accentHover : Theme.accent)
    Behavior on color { ColorAnimation { duration: 100 } }

    Text {
        anchors.centerIn: parent
        text: "读取"
        color: Theme.accentInk
        font.family: Theme.uiFont
        font.pixelSize: 11
    }
    Rectangle {
        objectName: btn.busyName
        visible: btn.busy > 0
        x: btn.width - 6
        y: -3
        width: 8
        height: 8
        radius: 4
        color: Theme.paper
        border.width: 2
        border.color: Theme.accent
        SequentialAnimation on opacity {
            running: btn.busy > 0
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.3; duration: 600 }
            NumberAnimation { from: 0.3; to: 1.0; duration: 600 }
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.host.readMode(btn.mode)
    }
}
