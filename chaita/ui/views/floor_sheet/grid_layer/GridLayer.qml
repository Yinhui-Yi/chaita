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

    // 长按抓起一格开始拖（FloorSheetWindow 接过去开小牌子）
    signal dragStart(int row, int col)
    // 短点清掉这一格（编辑模式下删一个坐标）
    signal cellCleared(int row, int col)

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
            ctx.strokeStyle = "rgba(40, 36, 30, 0.28)"
            ctx.lineWidth = 0.5
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
                ctx.lineWidth = 1.5
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
            ctx.lineWidth = 1.5
            for (var m = 0; m < multi.length; m++) {
                var mc = multi[m] || ({})
                ctx.strokeRect(Number(mc.col) * size + 2,
                               Number(mc.row) * size + 2,
                               size - 4, size - 4)
            }
        }
    }

    MouseArea {
        id: gesture
        anchors.fill: parent
        enabled: layer.editing
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        property point pressAt: Qt.point(0, 0)
        property bool dragging: false

        onPositionChanged: function (mouse) {
            if (gesture.dragging)
                return
            layer.host.gridHover = layer.cellAt(mouse.x, mouse.y)
        }
        onExited: {
            if (!gesture.dragging)
                layer.host.gridHover = ({})
        }
        onPressed: function (mouse) {
            gesture.pressAt = Qt.point(mouse.x, mouse.y)
            // Ctrl+点是"勾选"，不是拖拽：按得再久也不许变成拖。慢点一下就变成
            // 拖拽会话、这次点击被吞掉，看着就是"勾不上第二格"
            //（用户："现在ctrl不能连续选中了"）。
            if (!(mouse.modifiers & Qt.ControlModifier))
                longPress.restart()
        }
        onReleased: function (mouse) {
            longPress.stop()
            if (gesture.dragging) {
                gesture.dragging = false
                layer.host.gridDrag = ({})
                return
            }
            var cell = layer.cellAt(mouse.x, mouse.y)
            if (!layer.inside(cell))
                return                    // 13×13 之外不算格子，什么都不做
            // Ctrl+点：勾选 / 取消这一格（多选，一次性记给一个词条）
            //（用户："编辑模式下能不能加一个ctrl加点击多选？一次性添加多个坐标"）
            if (mouse.modifiers & Qt.ControlModifier) {
                layer.host.gridMultiToggle(cell.row, cell.col)
                return
            }
            // 短点：已占的格子**一步删掉**（用户："为什么不能删坐标"），
            // 空格子只是取消选中。选词条改名点词条那一行，不再靠点地图。
            var owner = layer.host.gridCellName(layer.floorName,
                                                cell.row, cell.col)
            if (owner === "")
                layer.host.gridSelect("")
            else
                layer.cellCleared(cell.row, cell.col)
        }
        onCanceled: {
            longPress.stop()
            gesture.dragging = false
            layer.host.gridDrag = ({})
        }

        Timer {
            id: longPress
            interval: 500
            onTriggered: {
                var cell = layer.cellAt(gesture.pressAt.x, gesture.pressAt.y)
                if (!layer.inside(cell))
                    return                // 出界：不起拖拽
                gesture.dragging = true
                layer.host.gridDrag = { "row": cell.row, "col": cell.col }
                layer.dragStart(cell.row, cell.col)
            }
        }
    }
}
