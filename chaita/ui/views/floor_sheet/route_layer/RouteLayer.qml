import QtQuick
// 先看 docs/UI_MAP.md / docs/ROUTE.md。这一份 = 地图上的路线提取层。
import "../../shared"

// 路线提取：长按玩家 = 起点（红点），鼠标进到相邻格就选一格、画一段红线；
// 走回头路是允许的（链上如实追加；回到上一格 = 撤销一步）。松手交差。
//
// 坐标都在**图像自己的坐标系**里（调用方把它铺满那张图就行），
// 格子边长由 `cell` 给（AI 读到的行列换算出来，读不到就 24）。
Item {
    id: layer

    property string floorName: ""
    // 一格多少像素（图像坐标）
    property real cell: 24
    // 起点格（行列）；-1 = 还没开始
    property int startRow: -1
    property int startCol: -1
    // 走过的格子，按顺序，**允许重复**（回头路）
    property var cells: []
    onCellsChanged: routeCanvas.requestPaint()
    property bool editing: false
    // 松手了：给出整条路线的格子
    signal finished(var cells)
    // 取消（Esc / 关窗）
    signal cancelled()

    function clear() {
        layer.cells = []
        layer.startRow = -1
        layer.startCol = -1
        layer.editing = false
        routeCanvas.requestPaint()
    }

    function cellAt(x, y) {
        return { "row": Math.floor(y / layer.cell),
                 "col": Math.floor(x / layer.cell) }
    }

    function sameCell(a, b) {
        return !!a && !!b && a.row === b.row && a.col === b.col
    }

    // 长按落在某点 = 定起点（红点）
    function startAt(x, y) {
        var cell = layer.cellAt(x, y)
        layer.startRow = cell.row
        layer.startCol = cell.col
        layer.cells = [cell]
        layer.editing = true
        routeCanvas.requestPaint()
    }

    // 鼠标挪到某点：只有进了**相邻**格才算一步
    function moveTo(x, y) {
        if (!layer.editing)
            return
        var cell = layer.cellAt(x, y)
        var last = layer.cells[layer.cells.length - 1]
        if (layer.sameCell(cell, last))
            return
        var prev = layer.cells[layer.cells.length - 2]
        if (layer.sameCell(cell, prev)) {
            // 回到上一格：撤销一步（不是新的一段路）
            layer.cells = layer.cells.slice(0, layer.cells.length - 1)
        } else if (Math.abs(cell.row - last.row) + Math.abs(cell.col - last.col) === 1) {
            // 四向相邻才接上；斜着/跳格忽略（免得画出一条穿墙线）
            layer.cells = layer.cells.concat([cell])
        }
        routeCanvas.requestPaint()
    }

    function finish() {
        if (!layer.editing)
            return
        layer.editing = false
        layer.finished(layer.cells.slice(0))
        routeCanvas.requestPaint()
    }

    // 格子中心（画线用）
    function centerOf(cell) {
        return Qt.point((cell.col + 0.5) * layer.cell,
                        (cell.row + 0.5) * layer.cell)
    }

    Canvas {
        id: routeCanvas
        anchors.fill: parent
        // 选中的样子：**红底 + 红框**（只描一圈线在地图上看不出来，用户：
        // "你画的格子完全不像选中状态"）；起点更重、还带一个实心点。
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            if (layer.cells.length === 0)
                return
            var size = layer.cell
            ctx.lineJoin = "round"
            ctx.lineCap = "round"
            // 走过的格子
            for (var i = 0; i < layer.cells.length; i++) {
                var cell = layer.cells[i]
                var first = i === 0
                ctx.fillStyle = first ? "rgba(194, 59, 46, 0.34)"
                                      : "rgba(194, 59, 46, 0.20)"
                ctx.fillRect(cell.col * size + 0.5, cell.row * size + 0.5,
                             size - 1, size - 1)
                ctx.strokeStyle = first ? Theme.markAtk
                                        : "rgba(194, 59, 46, 0.85)"
                ctx.lineWidth = first ? 2 : 1.5
                ctx.strokeRect(cell.col * size + 1, cell.row * size + 1,
                               size - 2, size - 2)
            }
            // 路线：2px 实线，拐点圆角
            ctx.strokeStyle = Theme.markAtk
            ctx.lineWidth = 2
            ctx.beginPath()
            for (var j = 0; j < layer.cells.length; j++) {
                var at = layer.centerOf(layer.cells[j])
                if (j === 0)
                    ctx.moveTo(at.x, at.y)
                else
                    ctx.lineTo(at.x, at.y)
            }
            ctx.stroke()
            // 起点：红点 + 白圈（一眼看出从哪一格起步）
            var start = layer.centerOf(layer.cells[0])
            var radius = Math.max(2.5, size * 0.18)
            ctx.beginPath()
            ctx.arc(start.x, start.y, radius, 0, 2 * Math.PI)
            ctx.fillStyle = Theme.markAtk
            ctx.fill()
            ctx.lineWidth = 1
            ctx.strokeStyle = Theme.paperHi
            ctx.stroke()
        }
    }

    // 手势：按下开始计时，500ms 没动就是长按；移动 / 松手都会打断计时
    MouseArea {
        id: gesture
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        property point pressAt: Qt.point(0, 0)
        property real armed: 0

        onPressed: function (mouse) {
            gesture.pressAt = Qt.point(mouse.x, mouse.y)
            gesture.armed = Date.now()
            longPress.restart()
            if (layer.editing)
                layer.moveTo(mouse.x, mouse.y)
        }
        onPositionChanged: function (mouse) {
            if (layer.editing) {
                longPress.stop()
                layer.moveTo(mouse.x, mouse.y)
            } else if (Math.abs(mouse.x - gesture.pressAt.x) > 6
                       || Math.abs(mouse.y - gesture.pressAt.y) > 6) {
                longPress.stop()
            }
        }
        onReleased: {
            longPress.stop()
            layer.finish()
        }
        onCanceled: {
            longPress.stop()
            layer.finish()
        }

        Timer {
            id: longPress
            interval: 500
            onTriggered: layer.startAt(gesture.pressAt.x, gesture.pressAt.y)
        }
    }
}
