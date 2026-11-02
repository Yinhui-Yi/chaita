import QtQuick
import "."

// 小胶囊：一小段文字装进圆角底（「剩 4」「破甲」「生命 80」「黄钥匙 1」这种）。
// 三种调子：neutral 灰底灰字；accent 蓝底蓝字（要强调的）；muted 更淡（已经没了/不用管）。
Rectangle {
    id: chip

    property string text: ""
    property string tone: "neutral"
    // 数字用等宽字体
    property bool mono: false
    property int fontSize: 11
    property bool bold: false

    implicitWidth: label.implicitWidth + 14
    implicitHeight: 20
    radius: height / 2
    color: chip.tone === "accent" ? Theme.accentSoft
         : (chip.tone === "muted" ? "transparent" : Theme.chip)
    border.width: chip.tone === "muted" ? 1 : 0
    border.color: Theme.hairline

    Text {
        id: label
        anchors.centerIn: parent
        text: chip.text
        color: chip.tone === "accent" ? Theme.accent
             : (chip.tone === "muted" ? Theme.ink3 : Theme.ink2)
        font.family: chip.mono ? Theme.monoFont : Theme.uiFont
        font.pixelSize: chip.fontSize
        font.bold: chip.bold
    }
}
