import QtQuick
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 一个扁按钮（描边 / 实心 amber / 危险三种），两个窗口共用。
// 配色/字体在上一层：qml/Theme.qml（qmldir 里注册成单例）
import ".."

// 一个扁按钮（描边 / 实心 amber / 危险三种）。
//
// 原来是 MainWindow.qml 里的 `component FlatBtn`，只有那份文件里能用；
// 伤害计算搬成 BattleWindow.qml 以后两边都要按钮，所以单独一份。
// 配色直接读 Theme 单例 —— 不用使用方再传一个 host 进来。
Rectangle {
    id: flat
    property string label: ""
    property bool solid: false
    property bool danger: false
    signal clicked()
    implicitWidth: flatText.implicitWidth + 18
    implicitHeight: 22
    radius: 6
    color: flat.solid
           ? (flatMouse.pressed ? "#9C6F1F"
              : (flatMouse.containsMouse ? "#A6771F" : Theme.amber))
           : (flatMouse.containsMouse
              ? (flat.danger ? "#F6E3DC" : Theme.paperLo) : "transparent")
    border.width: flat.solid ? 0 : 1
    border.color: flat.danger ? "#E3B7A8" : Theme.hairline
    Behavior on color { ColorAnimation { duration: 120 } }
    Text {
        id: flatText
        anchors.centerIn: parent
        text: flat.label
        color: flat.solid ? Theme.amberInk
             : (flat.danger ? Theme.danger : Theme.ink2)
        font.family: Theme.uiFont
        font.pixelSize: 9
        font.bold: flat.solid
    }
    MouseArea {
        id: flatMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: flat.clicked()
    }
}
