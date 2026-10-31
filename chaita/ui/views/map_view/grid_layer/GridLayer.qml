import QtQuick
// 格子编辑覆盖层：铺在地图截图那块矩形上（docs/ROUTE.md 之外的新模式）。
//
// 编辑模式开的时候：
//   · 画 13×13 坐标线（side 由调用方给，和 agent.map.read.SIDE 同一份规则）；
//   · 悬停哪格高亮哪格；
//   · 长按 500ms 抓起一格开始拖，拖到下方怪/资源词条上把坐标记给词条；
//   · 短点一格：已占的格子**一步删掉**（删坐标），空格子只是取消选中；
//   · Ctrl+点：勾上/取消（多选），之后长按拖是一次把整把坐标记给同一个词条；
//   · 13×13 之外不算格子：不出悬停、不抓、不删（截图区不一定是正好 13 格）。
//
// 颜色约定：**只有选中词条的格子是黄的**（用户："我没有选中的词条怎么图上也是黄的"），
// 别的词条占的格子用淡灰标出来（一眼看出被占了，但不抢"选中"这个意思）。
import "../../shared"

Item {
    id: layer

    // 主窗口（状态都在它身上）
    property var host
    property string floorName: ""
    // 一格多少像素（图像坐标，由 host.routeCell 算出来）
    property real cell: 24
    // 地图固定 13×13（和 agent.map.read.SIDE 同一份规则，由调用方传进来）
    property int side: 13
    // 编辑模式开没开（开了才画线、才有手势）
    property bool editing: false
    // 这一层 grid 的 cells（画"哪格已经有东西"）
    property var gridCells: []

    function inside(cell) {
        return !!cell && cell.row !== undefined && cell.col !== undefined
            && Number(cell.row) >= 0 && Number(cell.row) < layer.side
            && Number(cell.col) >= 0 && Number(cell.col) < layer.side
    }

    // 某个点落在哪一格；**13×13 之外返回空**（{}）。
    // 截图区不一定正好 13 格高/宽，不卡边界的话下面那片也能算出第 20 行这种
    // 脏坐标（用户："你怎么选出21，6的"）。
    function cellAt(x, y) {
        var cell = { "row": Math.floor(y / layer.cell),
                     "col": Math.floor(x / layer.cell) }
        return layer.inside(cell) ? cell : ({})
    }

    function hasContent(row, col) {
        for (var i = 0; i < layer.gridCells.length; i++) {
            var c = layer.gridCells[i] || ({})
            if (Number(c.row) === Number(row) && Number(c.col) === Number(col))
                return true
        }
        return false
    }

    // 悬停/拖拽/选中变了都要重画
    Connections {
        target: layer.host
        function onGridHoverChanged() { gridCanvas.requestPaint() }
        function onGridDragChanged() { gridCanvas.requestPaint() }
        function onGridSelectedChanged() { gridCanvas.requestPaint() }
        function onGridMultiChanged() { gridCanvas.requestPaint() }
    }
    onGridCellsChanged: gridCanvas.requestPaint()
    onEditingChanged: gridCanvas.requestPaint()
    // 尺寸变了必须重画：这张图现在挂在**可拉伸的地图窗口**上（`anchors.fill`），
    // 画布一开始是按 0×0 建出来的，不重画就一直是空的（坐标系看不见）
    onWidthChanged: gridCanvas.requestPaint()
    onHeightChanged: gridCanvas.requestPaint()
    onCellChanged: gridCanvas.requestPaint()

    Canvas {
        id: gridCanvas
        anchors.fill: parent
        visible: layer.editing
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            if (!layer.editing)
                return
            var n = 13
            var size = layer.cell
            var hover = (layer.host && layer.host.gridHover) || ({})
            var drag = (layer.host && layer.host.gridDrag) || ({})
            var selected = layer.host ? String(layer.host.gridSelected || "") : ""

            // 坐标系：13 条竖线 + 13 条横线
            // 0.5px 的深色线在 1.5 倍屏上会被抗锯齿吃掉（实测**看不见**），
            // 所以 1px + 深一点的墨色：看得清又不抢地图
            ctx.strokeStyle = "rgba(30, 26, 20, 0.45)"
            ctx.lineWidth = 1
            for (var i = 0; i <= n; i++) {
                var p = i * size
                ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, n * size)
                ctx.stroke()
                ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(n * size, p)
                ctx.stroke()
            }

            // 有内容的格子：选中的是黄底，别的词条淡灰底
            for (var j = 0; j < layer.gridCells.length; j++) {
                var g = layer.gridCells[j] || ({})
                var isSelected = selected !== ""
                              && String(g.name || "") === selected
                ctx.fillStyle = isSelected ? "rgba(214, 158, 46, 0.24)"
                                           : "rgba(0, 0, 0, 0.10)"
                ctx.fillRect(Number(g.col) * size, Number(g.row) * size,
                             size, size)
            }

            // 悬停的那一格：描边（正在拖就不画悬停，别两个框叠一起）
            if (hover.row !== undefined && drag.row === undefined) {
                ctx.strokeStyle = "rgba(214, 158, 46, 0.95)"
                ctx.lineWidth = 1
                ctx.strokeRect(Number(hover.col) * size + 1,
                               Number(hover.row) * size + 1,
                               size - 2, size - 2)
            }

            // 正在拖的那一格：实框
            if (drag.row !== undefined) {
                ctx.strokeStyle = Theme.amber
                ctx.lineWidth = 2
                ctx.strokeRect(Number(drag.col) * size + 1,
                               Number(drag.row) * size + 1,
                               size - 2, size - 2)
            }

            // 多选勾中的格子：琥珀色细框（和"正在拖"的粗框区分开）
            var multi = (layer.host && layer.host.gridMulti) || []
            ctx.strokeStyle = Theme.amber
            ctx.lineWidth = 1
            for (var m = 0; m < multi.length; m++) {
                var mc = multi[m] || ({})
                ctx.strokeRect(Number(mc.col) * size + 2,
                               Number(mc.row) * size + 2,
                               size - 4, size - 4)
            }
        }
    }


    // 只做悬停高亮：**点击/长按都归路线层**（它是地图上唯一收鼠标的一层）。
    // 以前这一层自己在上面收点击，编辑模式一开就把长按住吃掉了，路线起不了笔
    // （用户 2026-10-31："长按拖动也无效"）。
    MouseArea {
        id: gesture
        anchors.fill: parent
        enabled: layer.editing
        acceptedButtons: Qt.NoButton
        hoverEnabled: true

        onPositionChanged: function (mouse) {
            layer.host.gridHover = layer.cellAt(mouse.x, mouse.y)
        }
        onExited: layer.host.gridHover = ({})
    }
}
