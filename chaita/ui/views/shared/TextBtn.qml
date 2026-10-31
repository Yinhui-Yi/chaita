import QtQuick
import "."

// 一句话就能点的小动作（"清单"「编辑」「刷新」「↑ 楼梯」「清空」「粘贴」这种）。
//
// 为什么要一个共用件（用户 2026-10-30："设计要统一！！！！"）：这些小动作以前是
// 每个界面各自 `Text + MouseArea` 手写一遍，字号 9/10、悬停色 ink2/ink3/amber
// 各不相同，同一排按钮看着就不是一套。规矩收到这里：**9px、ink3、悬停 ink，
// 要强调就 accent 成琥珀色**，热区往外放 4px（看得见的位置点得中）。
Item {
    id: btn

    // 文字
    property string text: ""
    // 亮起来的颜色（默认悬停变墨色；传 Theme.amber 这类就一直是那个颜色）
    property color accent: "transparent"
    // 常亮（比如"正在编辑"这种状态）：文字用 accent 色
    property bool active: false
    // 禁用（灰掉且点不动）
    property bool disabled: false

    signal clicked()

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    width: implicitWidth
    height: implicitHeight
    opacity: btn.disabled ? 0.45 : 1.0

    Text {
        id: label
        anchors.fill: parent
        text: btn.text
        color: btn.active && btn.accent !== "transparent" ? btn.accent
             : (btn.disabled ? Theme.ink3
             : (mouse.containsMouse
                ? (btn.accent !== "transparent" ? btn.accent : Theme.ink)
                : Theme.ink3))
        font.family: Theme.uiFont
        font.pixelSize: 9
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
