import QtQuick
import "."

// 「读取」按钮：标签页右上角那颗实心琥珀按钮，地图页和怪物页各放一颗。
// 字永远写「读取」：手册分页，翻到下一页还得再点它；写成「读取中」会让人以为
// 不能再按（用户："要通过按读取中来开启第二页太反直觉"）。
// 正在读用右上角一颗呼吸的小点表示，按钮本身照样能点（可并行读取）。
Rectangle {
    id: btn

    // 归属：主窗口（runningCount / readMode 在它身上）
    property var host
    // 读什么："map" / "monsters"
    property string mode: ""
    readonly property int busy: host ? host.runningCount(btn.mode) : 0

    width: 46
    height: 20
    radius: 6
    color: Theme.amber

    Text {
        anchors.centerIn: parent
        text: "读取"
        color: Theme.amberInk
        font.family: Theme.uiFont
        font.pixelSize: 10
        font.bold: true
    }
    Rectangle {
        objectName: btn.objectName + "Busy"
        visible: btn.busy > 0
        x: btn.width - 7
        y: -2
        width: 7
        height: 7
        radius: 3.5
        color: Theme.amberInk
        border.width: 1
        border.color: Theme.amber
        SequentialAnimation on opacity {
            running: btn.busy > 0
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.3; duration: 600 }
            NumberAnimation { from: 0.3; to: 1.0; duration: 600 }
        }
    }
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.host.readMode(btn.mode)
    }
}
