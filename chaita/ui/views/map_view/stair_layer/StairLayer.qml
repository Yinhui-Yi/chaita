import QtQuick
// 楼梯层：这一层**所有**楼梯都画出来（一层可以有好几个，用户："谁告诉你一层
// 只有一个上楼或下楼的？"）。每个楼梯自己带 `to`（通到哪一层），徽章上用
// 方向图 + 一点点目标层号表示。
//
// 位置/目标层都不在这儿改（用户 2026-10-30："上下层写清单里！！！！"）：清单里
// 一行一个楼梯，拖图上格子定位置、点「目标层」选去哪。这一层只负责画。
//
// 颜色沿用全项目的三色语义：↑ 上楼 = 绿（markMdef），↓ 下楼 = 蓝（markDef）。
//
// **标记的位置/大小上在 `badges` 里一次算好**（格子边长会随窗口变），
// 委托只管画：委托拿不到外面的 id（实测 `layer.cell` 在委托里是空）。
import "../../shared"

Item {
    id: layer

    // `[{row, col, dir, to}]`（`row = -1` = 还没标位置，不画）
    property var stairs: []
    // 一格多少像素（图像坐标）
    property real cell: 24
    // 两个方向的楼梯图（`assets/items/stair_up|down.png`，外面传进来）
    property string upSrc: ""
    property string downSrc: ""

    function colorOf(dir) {
        return String(dir) === "up" ? Theme.markMdef : Theme.markDef
    }

    // 目标层只显示层号（"通天塔3" → "3"）：徽章上放不下全名
    function shortTarget(to) {
        var text = String(to || "")
        var digits = /(\d+)\s*$/.exec(text)
        if (digits)
            return digits[1]
        return text
    }

    readonly property var badges: {
        var out = []
        var list = layer.stairs || []
        var size = Math.max(4, layer.cell)
        for (var i = 0; i < list.length; i++) {
            var one = list[i] || {}
            var row = Number(one.row)
            var col = Number(one.col)
            if (!(row >= 0 && col >= 0))
                continue                  // 还没标位置
            var dir = String(one.dir || "up")
            out.push({ "dir": dir,
                       "name": "stairMark" + (dir === "up" ? "Up" : "Down"),
                       "arrow": dir === "up" ? "↑" : "↓",
                       "src": dir === "up" ? layer.upSrc : layer.downSrc,
                       "color": layer.colorOf(dir),
                       "to": layer.shortTarget(one.to),
                       "x": Number(col) * size,
                       "y": Number(row) * size,
                       "size": size,
                       "font": Math.max(9, Math.round(size * 0.62)) })
        }
        return out
    }

    Repeater {
        model: layer.badges
        delegate: Rectangle {
            objectName: modelData.name
            x: modelData.x
            y: modelData.y
            width: modelData.size
            height: modelData.size
            radius: 3
            color: Qt.rgba(1, 1, 1, 0.16)
            border.width: 2
            border.color: modelData.color
            // 图上就是素材库那张楼梯（和清单里同一张），外圈颜色只区分上/下
            Image {
                id: badge
                anchors.fill: parent
                anchors.margins: 1
                source: String(modelData.src || "")
                visible: status === Image.Ready
                fillMode: Image.PreserveAspectFit
                smooth: false
            }
            Text {
                anchors.centerIn: parent
                visible: badge.status !== Image.Ready
                text: modelData.arrow
                color: modelData.color
                font.family: Theme.uiFont
                font.pixelSize: modelData.font
                font.bold: true
            }
            // 目标层号：贴在格子右下角，一眼看出这个楼梯通哪
            Text {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: -1
                anchors.bottomMargin: -3
                text: String(modelData.to || "")
                color: modelData.color
                font.family: Theme.monoFont
                font.pixelSize: Math.max(7, Math.round(modelData.size * 0.32))
                font.bold: true
            }
        }
    }
}
