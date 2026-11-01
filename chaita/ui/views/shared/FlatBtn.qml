import QtQuick
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 一个扁按钮（描边 / 实心 accent / 危险三种），两个窗口共用。
// 配色/字体在上一层：qml/Theme.qml（qmldir 里注册成单例）
import ".."

// 一个扁按钮（描边 / 实心强调色 / 危险三种）。
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
    implicitWidth: flatText.implicitWidth + 20
    implicitHeight: Theme.controlH
    radius: Theme.radius
    color: flat.solid
           ? (flatMouse.pressed ? Theme.accentPress
              : (flatMouse.containsMouse ? Theme.accentHover : Theme.accent))
           : (flatMouse.pressed ? Theme.hover
              : (flatMouse.containsMouse
                 ? (flat.danger ? Theme.dangerSoft : Theme.paperLo) : Theme.paper))
    border.width: flat.solid ? 0 : 1
    border.color: flat.danger ? Theme.dangerEdge : Theme.fieldEdge
    Behavior on color { ColorAnimation { duration: 100 } }
    Text {
        id: flatText
        anchors.centerIn: parent
        text: flat.label
        color: flat.solid ? Theme.accentInk
             : (flat.danger ? Theme.danger : Theme.ink)
        font.family: Theme.uiFont
        font.pixelSize: 11
    }
    MouseArea {
        id: flatMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: flat.clicked()
    }
}
