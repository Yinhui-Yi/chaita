import QtQuick
import "."

// 一张卡：白底圆角 + 细外框 + 底沿一线暗边（像浮在灰底上）。
// 主界面的状态 / 地图 / 怪物 / 技能 / 读取记录 / 对话各占一张。
//
// 往里面写的子项会进一个竖排的 Column，宽度 = 卡宽 − 两边内边距；
// 子项不可见时 Column 会让位，所以卡的高度跟着内容走（`implicitHeight`）。
Rectangle {
    id: card

    // 内边距
    property int pad: 10
    default property alias content: col.data

    implicitHeight: col.implicitHeight + card.pad * 2
    radius: 8
    color: Theme.paper
    border.width: 1
    border.color: Theme.cardEdge

    // 底沿的暗边：比卡片整体矮 1px 地垫在下面
    Rectangle {
        z: -1
        anchors.fill: parent
        anchors.topMargin: 2
        anchors.bottomMargin: -1
        radius: card.radius
        color: Theme.cardShade
    }

    Column {
        id: col
        x: card.pad
        y: card.pad
        width: card.width - card.pad * 2
        spacing: 0
    }
}
