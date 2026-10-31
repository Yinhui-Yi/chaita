import QtQuick
// 先看 docs/UI_MAP.md / docs/ROUTE.md。这一份 = 地图上的路线提取层。
import "../../shared"

// 路线提取：长按玩家 = 起点（红点），鼠标进到相邻格就选一格、画一段红线；
// 走回头路是允许的：退到走过的任何一格都如实追加（用户 2026-10-29 拍板，
// 前进一格再后退一格也要记成来回两段，不再撤销）。松手交差。
//
// **跨层**（用户 2026-10-30：「我设想的换层是将人物移动到楼梯才上层或下层」）：
// 贴边翻层那一套已经删了。走到楼梯格由外面的 `onStepped` 决定换不换层，
// 换层时它调 `jumpTo()` 把路线在另一层的落点接上，然后接着拖。
// 每格记一个 `floor`，线只画**当前这一层**的格子，换层前的格子留着不丢。
//
// 坐标都在**图像自己的坐标系**里（调用方把它铺满那张图就行），
// 格子边长由 `cell` 给（AI 读到的行列换算出来，读不到就 24）。
Item {
    id: layer

    property string floorName: ""
    // 现在这一层是哪一层（外面换地图时跟着改）
    property string cellFloor: ""
    // 一格多少像素（图像坐标）
    property real cell: 24
    // 起点格（行列）；-1 = 还没开始
    property int startRow: -1
    property int startCol: -1
    // 走过的格子，按顺序，**允许重复**（回头路）
    property var cells: []
    onCellsChanged: routeCanvas.requestPaint()
    // 窗口拉大/拉小之后线要按新尺寸重画（画布不会自己知道）
    onWidthChanged: routeCanvas.requestPaint()
    onHeightChanged: routeCanvas.requestPaint()
    onCellChanged: routeCanvas.requestPaint()
    property bool editing: false
    // 这一下点击归不归它：标楼梯的时候要让给楼梯层（不然点下去是起一条路线）
    property bool clickable: true
    // 每走进一格上报一次：外面按它判断"这一格是不是楼梯、要不要换层"
    signal stepped(var cell)
    // 短按（没长按起笔）松手：编辑模式里是"选中这一格"，平时是"点楼梯换层"。
    // 用户 2026-10-31："现在地图上点击楼梯也要能换层" —— 不拖也能切。
    // **整个地图只有这一层收鼠标**（格子层只画、只做悬停），所以编辑模式下
    // 长按拖路线也不会被格子层吃掉（用户："长按拖动也无效"）。
    signal tapped(var cell, int modifiers)
    // 右键：编辑模式下出小窗（复制坐标 / 清掉）
    signal rightTapped(var cell, real x, real y)
    // 长按到点了：**外面决定这是"画路线"还是"抓起这一格拖进清单"**
    // （编辑模式 = 抓格子拖，平时 = 画路线）
    signal longPressed(real x, real y)
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
                 "col": Math.floor(x / layer.cell),
                 "floor": layer.cellFloor }
    }

    function sameCell(a, b) {
        return !!a && !!b && a.row === b.row && a.col === b.col
               && String(a.floor || "") === String(b.floor || "")
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

    // 鼠标挪到某点：只有进了**相邻**格才算一步；退到走过的格也照记（回头路）
    function moveTo(x, y) {
        if (!layer.editing)
            return
        var cell = layer.cellAt(x, y)
        var last = layer.cells[layer.cells.length - 1]
        if (layer.sameCell(cell, last))
            return
        if (Math.abs(cell.row - last.row) + Math.abs(cell.col - last.col) === 1) {
            // 四向相邻才接上；斜着/跳格忽略（免得画出一条穿墙线）
            layer.cells = layer.cells.concat([cell])
            routeCanvas.requestPaint()
            layer.stepped(cell)
        }
    }

    // 换层之后接着画：从另一层的某个楼梯格重新起笔（这一格也算走过）。
    // 落点不要求和上一格相邻（它在另一张图上），但照样进链，线从它往后接。
    function jumpTo(floorText, row, col) {
        if (!layer.editing)
            return
        var floor = String(floorText || "")
        var atRow = Number(row)
        var atCol = Number(col)
        if (!isFinite(atRow) || !isFinite(atCol))
            return
        layer.cellFloor = floor
        layer.cells = layer.cells.concat([{ "row": Math.round(atRow),
                                            "col": Math.round(atCol),
                                            "floor": floor }])
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
            // 走过的格子（只画**当前这一层**的；换过层的留在 cells 里但这里跳过）
            for (var i = 0; i < layer.cells.length; i++) {
                var cell = layer.cells[i]
                if (String(cell.floor || "") !== String(layer.cellFloor || ""))
                    continue
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
            var started = false
            for (var j = 0; j < layer.cells.length; j++) {
                var one = layer.cells[j]
                if (String(one.floor || "") !== String(layer.cellFloor || ""))
                    continue
                var at = layer.centerOf(one)
                if (!started) {
                    ctx.moveTo(at.x, at.y)
                    started = true
                } else {
                    ctx.lineTo(at.x, at.y)
                }
            }
            ctx.stroke()
            // 起点：红点 + 白圈（一眼看出从哪一格起步；换层后起点不在这张图上）
            var start = layer.cells[0]
            if (String(start.floor || "") === String(layer.cellFloor || "")) {
                var middle = layer.centerOf(start)
                var radius = Math.max(2.5, size * 0.18)
                ctx.beginPath()
                ctx.arc(middle.x, middle.y, radius, 0, 2 * Math.PI)
                ctx.fillStyle = Theme.markAtk
                ctx.fill()
                ctx.lineWidth = 1
                ctx.strokeStyle = Theme.paperHi
                ctx.stroke()
            }
        }
    }

    // 手势：按下开始计时，350ms 没动就是长按起笔；移动 / 松手都会打断计时
    MouseArea {
        id: gesture
        anchors.fill: parent
        hoverEnabled: true
        // 左键画路线/点格子，右键出小窗（编辑模式）
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        // 地图现在长在主界面的 `flick`（Flickable）里：不给这一句，长按起笔之后的
        // 拖动会被 Flickable 抢去当"翻页"，路线一格也画不出来（用户："我选不了路线"）。
        // 地图上就是用来画路线/抓格子的，滚页面请用滚轮。
        preventStealing: true
        enabled: layer.clickable
        property point pressAt: Qt.point(0, 0)
        property bool moved: false
        property bool rightPress: false
        property int pressModifiers: Qt.NoModifier

        onPressed: function (mouse) {
            gesture.pressAt = Qt.point(mouse.x, mouse.y)
            gesture.moved = false
            gesture.pressModifiers = mouse.modifiers
            gesture.rightPress = (mouse.button === Qt.RightButton)
            if (gesture.rightPress)
                return                      // 右键：等松手出小窗，不起笔
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
                gesture.moved = true
                longPress.stop()
            }
        }
        onReleased: {
            longPress.stop()
            if (gesture.rightPress) {
                layer.rightTapped(layer.cellAt(gesture.pressAt.x,
                                               gesture.pressAt.y),
                                  gesture.pressAt.x, gesture.pressAt.y)
                return
            }
            if (layer.editing) {
                layer.finish()
                return
            }
            // 没起笔、也没挪动 = 就是点了一下：把这一格报上去
            // （编辑模式里是"选中这一格"，平时是"点楼梯换层"）
            if (!gesture.moved) {
                layer.tapped(layer.cellAt(gesture.pressAt.x, gesture.pressAt.y),
                             gesture.pressModifiers)
            }
        }
        onCanceled: {
            longPress.stop()
            layer.finish()
        }

        Timer {
            id: longPress
            // 350ms：500ms 要按住不动太久，手一抖就起不了笔（用户："我选不了路线"）
            interval: 350
            onTriggered: layer.longPressed(gesture.pressAt.x, gesture.pressAt.y)
        }
    }
}
