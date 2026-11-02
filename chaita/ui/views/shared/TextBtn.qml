import QtQuick
import "."

// 一句话就能点的小动作（"清单"「编辑」「刷新」「↑ 楼梯」「清空」「粘贴」这种）。
//
// 为什么要一个共用件（用户 2026-10-30："设计要统一！！！！"）：这些小动作以前是
// 每个界面各自 `Text + MouseArea` 手写一遍，字号、悬停色各不相同，同一排按钮
// 看着就不是一套。规矩收到这里：**10px、ink3、悬停 ink，要强调就传 accent
// （强调蓝）**，热区往外放 4px（看得见的位置点得中）。
Item {
    id: btn

    // 文字
    property string text: ""
    // 亮起来的颜色（默认悬停变墨色；传 Theme.accent 这类就一直是那个颜色）
    property color accent: "transparent"
    // 常亮（比如"正在编辑"这种状态）：文字用 accent 色
    property bool active: false
    // 禁用（灰掉且点不动）
    property bool disabled: false

    // 药丸样式：左右留白 + 悬停浅灰底（成排的小动作用，比如地图底下那一排）
    property bool pill: false

    signal clicked()

    readonly property int padX: btn.pill ? 8 : 0
    implicitWidth: label.implicitWidth + btn.padX * 2
    implicitHeight: btn.pill ? 22 : label.implicitHeight
    width: implicitWidth
    height: implicitHeight
    opacity: btn.disabled ? 0.45 : 1.0

    Rectangle {
        anchors.fill: parent
        radius: Theme.radius
        color: btn.pill && btn.active ? Theme.accentSoft
             : (btn.pill && mouse.containsMouse ? Theme.hover : "transparent")
        Behavior on color { ColorAnimation { duration: 100 } }
    }

    Text {
        id: label
        anchors.fill: parent
        anchors.leftMargin: btn.padX
        anchors.rightMargin: btn.padX
        horizontalAlignment: btn.pill ? Text.AlignHCenter : Text.AlignLeft
        verticalAlignment: btn.pill ? Text.AlignVCenter : Text.AlignTop
        text: btn.text
        color: btn.active && btn.accent !== "transparent" ? btn.accent
             : (btn.disabled ? Theme.ink3
             : (mouse.containsMouse
                ? (btn.accent !== "transparent" ? btn.accent : Theme.ink)
                : (btn.pill ? Theme.ink2 : Theme.ink3)))
        font.family: Theme.uiFont
        font.pixelSize: btn.pill ? 11 : 10
        font.bold: btn.active
        elide: Text.ElideRight
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        anchors.margins: -4
        hoverEnabled: true
        enabled: !btn.disabled
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }
}
