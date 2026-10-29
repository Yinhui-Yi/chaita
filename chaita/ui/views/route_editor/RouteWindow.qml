import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
// 先看 docs/UI_MAP.md / docs/ROUTE.md：哪份文件画哪个界面、状态在谁身上。
// 配色/按钮在上一层：views/shared（Theme 单例 + FlatBtn）
import "../shared"
// 它自己的下拉菜单（一个界面一个文件夹）
import "pick_menu"
// 它自己的改参数卡片（和伤害计算点缩略图出来的一样）
import "edit_card"

// 路线链（docs/ROUTE.md）：勇者 → 缩略图 → 缩略图 … 一条横链，摆不下就折行。
// 只摆怪/宝石/血瓶（空的走过格不摆），掉血写在格后、总掉血在右端。
// 公式在 `chaita/game/battle.py` —— 和伤害计算共用同一份（`battle.run_plan`）。
//
// 它是**一扇真窗口**（无边框 + 置顶 + Qt.Tool，和伤害计算同一个形状），能摆在
// 游戏旁边边看边走。状态都在主窗口的 `route*` 上，这里读 `host.xxx`。
Window {
    id: routeWin
    // 主窗口（共享工具 + controller 都在它身上）
    property var host
    // 这一扇窗自己的上下文（floor/index/cells/结果/菜单/编辑），多开各管各的
    property var ctx: ({})

    // Ctrl+C 复制路线（和按钮「复制」同一件事，写系统剪贴板）
    Shortcut {
        sequence: "Ctrl+C"
        onActivated: host.routeCopy(ctx)
    }

    objectName: "routeWindow"
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    readonly property var screenRect: {
        var scr = routeWin.screen
        if (!scr)
            return Qt.rect(0, 0, 1920, 1080)
        var originX = scr.virtualX !== undefined ? scr.virtualX : 0
        var originY = scr.virtualY !== undefined ? scr.virtualY : 0
        return Qt.rect(originX, originY, scr.width, scr.height)
    }
    // 抬头 28 + 人物一行 20 + 间距；链最少 40（一格行高）
    readonly property int headH: 54
    readonly property int autoW: 420
    readonly property int autoH: headH + 8
        + Math.min(300, Math.max(38, chainCol.implicitHeight))
    readonly property int maxH: Math.max(170, screenRect.height - 72)
    // 点开格子菜单时窗口长高一截（菜单挂在格子下面，得放得下）；拉过就按拉的来
    readonly property int autoHeight: Math.min(maxH, autoH
        + (ctx.menu !== "" ? 210 : 0))

    // 用户："路线图的窗口不能拉伸" —— 宽高都能拉（和伤害计算同一套手柄）
    width: Math.max(320, ctx.winW > 0 ? ctx.winW : autoW)
    height: Math.max(170, ctx.winH > 0 ? ctx.winH : autoHeight)

    // 整块钳在屏幕里（拖抬头以后不会掉出去）
    function clampPos() {
        var rect = routeWin.screenRect
        if (!rect)
            return
        var left = rect.x + 2
        var top = rect.y + 2
        var right = Math.max(left, rect.x + rect.width - routeWin.width - 2)
        var bottom = Math.max(top, rect.y + rect.height - routeWin.height - 2)
        routeWin.x = Math.round(Math.max(left, Math.min(routeWin.x, right)))
        routeWin.y = Math.round(Math.max(top, Math.min(routeWin.y, bottom)))
    }

    // 开窗时摆在主窗口右边（和伤害计算同一个落点规矩）
    function place() {
        var rect = routeWin.screenRect
        if (!rect)
            return
        routeWin.x = Math.round(Math.max(
            rect.x + 4,
            Math.min(host.x + host.width + 8,
                     rect.x + rect.width - routeWin.width - 12)))
        routeWin.y = Math.round(Math.max(
            rect.y + 4,
            Math.min(host.y + 60,
                     rect.y + rect.height - routeWin.height - 12)))
    }

    // 点开的格子菜单挂在那一格下面。链会折行，所以位置从**那一格自己的坐标**
    // 换算过来（格子在 Flickable 里，mapToItem 会带上 contentY）。
    function cellChip(cellIndex) {
        var list = chainFlow.children
        for (var i = 0; i < list.length; i++) {
            var child = list[i]
            if (child.objectName === "routeCellChip"
                    && child.cellIndex === cellIndex)
                return child
        }
        return null
    }
    function placeMenu() {
        if (ctx.menu === "" || ctx.menuCell < 0)
            return
        var chip = cellChip(ctx.menuCell)
        if (!chip)
            return
        var point = chip.mapToItem(cardBox, 0, 0)
        var below = cardBox.height - (point.y + chip.height) - 6
        var above = point.y - 6
        // 先按"放得下"算高度（选项列表可以缩），再决定挂在格子下面还是上面
        var room = Math.max(below, above)
        routeMenuLayer.maxListH = Math.max(26, Math.min(240, room - 84))
        var menuH = routeMenuLayer.menuHeight()
        var y = point.y + chip.height + 2
        if (y + menuH > cardBox.height - 4)
            y = Math.max(4, point.y - menuH - 2)
        ctx.menuX = Math.round(Math.max(4, Math.min(point.x,
                                                        cardBox.width - 254)))
        ctx.menuY = Math.round(y)
    }

    Shortcut {
        sequence: "Esc"
        onActivated: host.closeRoute(ctx)
    }
    onActiveChanged: {
        if (!routeWin.active)
            host.closeRouteMenu(ctx)
    }

    // ---- 拉大小：四条边 + 四个角都能拉（用户："路线图的窗口不能拉伸"）----
    // 和伤害计算同一套算法（BattleGrip）：位移用**屏幕坐标**，拉出来的尺寸记进
    // ctx.winW/H —— 窗口宽高是绑定出来的，不记的话绑定会把它顶回去。
    component RouteGrip: Item {
        id: grip
        property bool pullLeft: false
        property bool pullRight: false
        property bool pullTop: false
        property bool pullBottom: false
        property bool marks: false

        Repeater {
            model: grip.marks ? [4, 9, 14] : []
            delegate: Rectangle {
                width: 11
                height: 1
                color: gripMouse.containsMouse ? Theme.amber : Theme.ink3
                opacity: 0.6
                x: grip.width - width - 1
                y: grip.height - modelData
                rotation: -45
                transformOrigin: Item.Right
            }
        }

        MouseArea {
            id: gripMouse
            anchors.fill: parent
            cursorShape: {
                var horizontal = grip.pullLeft || grip.pullRight
                var vertical = grip.pullTop || grip.pullBottom
                if (horizontal && vertical)
                    return grip.pullLeft === grip.pullTop
                           ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
                return horizontal ? Qt.SizeHorCursor : Qt.SizeVerCursor
            }
            property real pressX: 0
            property real pressY: 0
            property real startX: 0
            property real startY: 0
            property real startW: 0
            property real startH: 0
            onPressed: function (m) {
                var at = mapToGlobal(m.x, m.y)
                pressX = at.x
                pressY = at.y
                startX = routeWin.x
                startY = routeWin.y
                startW = routeWin.width
                startH = routeWin.height
            }
            onPositionChanged: function (m) {
                if (!pressed)
                    return
                var at = mapToGlobal(m.x, m.y)
                var dx = at.x - pressX
                var dy = at.y - pressY
                var w = startW + (grip.pullRight ? dx : 0)
                             - (grip.pullLeft ? dx : 0)
                var h = startH + (grip.pullBottom ? dy : 0)
                             - (grip.pullTop ? dy : 0)
                w = Math.max(320, Math.min(routeWin.screenRect.width - 8, w))
                h = Math.max(170, Math.min(routeWin.maxH, h))
                // 从上边/左边拉：窗口原点跟着动，另一侧才不动
                var x = grip.pullLeft ? startX + (startW - w) : startX
                var y = grip.pullTop ? startY + (startH - h) : startY
                ctx.winW = Math.round(w)
                ctx.winH = Math.round(h)
                routeWin.x = Math.round(x)
                routeWin.y = Math.round(y)
                routeWin.clampPos()
            }
        }
    }

    Rectangle {
        id: cardBox
        objectName: "routeCard"
        anchors.fill: parent
        radius: 8
        color: Theme.paperHi
        border.width: 1
        border.color: Theme.edge
        clip: true
        MouseArea { anchors.fill: parent }

        // ---- 抬头：拖着走 + 关 ----
        Item {
            id: routeHeader
            x: 6
            y: 2
            width: parent.width - 12
            height: 28
            MouseArea {
                id: routeDrag
                objectName: "routeDrag"
                anchors.fill: parent
                property real pressX: 0
                property real pressY: 0
                property real startX: 0
                property real startY: 0
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.ArrowCursor
                onPressed: function (m) {
                    var at = mapToGlobal(m.x, m.y)
                    pressX = at.x
                    pressY = at.y
                    startX = routeWin.x
                    startY = routeWin.y
                }
                onPositionChanged: function (m) {
                    if (!pressed)
                        return
                    var at = mapToGlobal(m.x, m.y)
                    routeWin.x = Math.round(startX + (at.x - pressX))
                    routeWin.y = Math.round(startY + (at.y - pressY))
                    routeWin.clampPos()
                }
            }
            Text {
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: "路线链"
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 0.6
            }
            Text {
                objectName: "routeFloorLabel"
                anchors.left: parent.left
                anchors.leftMargin: 52
                anchors.verticalCenter: parent.verticalCenter
                text: ctx.floor
                color: Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 10
                elide: Text.ElideRight
                width: Math.min(implicitWidth, 90)
            }
            Text {
                objectName: "routeCopy"
                anchors.right: routeDeleteText.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: "复制"
                color: copyMouse.containsMouse ? Theme.amber : Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 9
                MouseArea {
                    id: copyMouse
                    anchors.fill: parent
                    anchors.margins: -4
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.routeCopy(ctx)
                }
            }
            Text {
                id: routeDeleteText
                objectName: "routeDelete"
                anchors.right: routeClose.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: "删"
                color: deleteMouse.containsMouse ? Theme.danger : Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 9
                MouseArea {
                    id: deleteMouse
                    anchors.fill: parent
                    anchors.margins: -4
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.routeRemove(ctx)
                }
            }
            Item {
                id: routeClose
                objectName: "routeClose"
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 16
                height: 16
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: routeCloseMouse.containsMouse
                           ? Theme.danger : Theme.ink3
                    font.pixelSize: 11
                }
                MouseArea {
                    id: routeCloseMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.closeRoute(ctx)
                }
            }
        }

        // ---- 用哪个人物在算：血/攻/防/魔防（状态行读到的，打开/计算时刷新） ----
        Text {
            id: routeHeroLine
            objectName: "routeHeroLine"
            x: 10
            y: 30
            width: parent.width - 20
            height: 20
            verticalAlignment: Text.AlignVCenter
            text: "血 " + host.fmt(ctx.hero.hp)
                  + "  ·  攻 " + host.fmt(ctx.hero.atk)
                  + "  ·  防 " + host.fmt(ctx.hero.def)
                  + "  ·  魔防 " + host.fmt(ctx.hero.mdef)
            color: Theme.ink2
            font.family: Theme.uiFont
            font.pixelSize: 9
            elide: Text.ElideRight
        }

        // ---- 链：勇者 → 格1,1 → 格1,2 …（摆不下折行） ----
        Flickable {
            id: routeFlick
            objectName: "routeFlick"
            x: 10
            y: routeWin.headH
            width: parent.width - 20
            height: Math.max(38, cardBox.height - routeWin.headH - 8)
            contentWidth: width
            contentHeight: chainCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            onContentYChanged: host.routeMenuPlace(ctx)

            Column {
                id: chainCol
                width: routeFlick.width
                spacing: 4

                Text {
                    objectName: "routeEmpty"
                    visible: (ctx.cells || []).length === 0
                    width: chainCol.width
                    height: visible ? 30 : 0
                    verticalAlignment: Text.AlignVCenter
                    text: "这条路线没有格子。回地图上长按玩家再拖一次。"
                    color: Theme.ink3
                    font.family: Theme.uiFont
                    font.pixelSize: 9
                }

                // 链照伤害计算的样子：勇者 → 缩略图 → 缩略图 …
                // 每格一个箭头 + 一张缩略图，掉血写在格后；只摆怪/宝石/血瓶，
                // 空的走过格不摆（用户："仿照伤害计算""非怪和宝石血瓶不需要显示"）。
                Flow {
                    id: chainFlow
                    objectName: "routeChain"
                    // 右边留 92px 给总掉血/剩血（和伤害计算一样钉在链右边）
                    width: chainCol.width - 92
                    spacing: 4

                    // 开头永远是勇者
                    Item {
                        objectName: "routeChainHero"
                        width: 16
                        height: 26
                        Image {
                            anchors.centerIn: parent
                            width: 16
                            height: 16
                            source: host.heroIcon
                            visible: source !== ""
                            fillMode: Image.PreserveAspectFit
                            smooth: false
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: !host.hasUrl(host.heroIcon)
                            text: "勇"
                            color: Theme.ink2
                            font.family: Theme.uiFont
                            font.pixelSize: 9
                        }
                    }

                    // 一格 = 箭头 + 缩略图 + 掉血（格后）
                    Repeater {
                        model: ctx.chainRows || []
                        delegate: Item {
                            id: stepItem
                            objectName: "routeCellChip"
                            property int cellIndex: modelData.index
                            readonly property var cell: modelData.cell || ({})
                            readonly property string icon: host.routeCellIcon(cell)
                            readonly property string glyph: host.routeCellGlyph(cell)
                            width: stepRow.implicitWidth
                            height: 26
                            // 点这一格（缩略图/掉血那一段）：改这一格的参数。
                            // 放在 Row **前面**，让箭头那块先被箭头自己的 MouseArea 吃掉 ——
                            // 和伤害计算同一个分工：点箭头 = 换这一格是什么，
                            // 点缩略图 = 改参数。
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: host.routeEditStep(ctx, modelData.index)
                            }
                            Row {
                                id: stepRow
                                spacing: 2
                                ChainArrow {
                                    objectName: "routeCellArrow"
                                    onClicked: host.openRouteMenu(ctx, stepItem.cellIndex)
                                }
                                Item {
                                    width: 14
                                    height: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    Image {
                                        anchors.fill: parent
                                        source: stepItem.icon
                                        visible: source !== ""
                                        fillMode: Image.PreserveAspectFit
                                        smooth: false
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        visible: stepItem.icon === ""
                                        text: stepItem.glyph
                                        color: Theme.ink2
                                        font.family: Theme.uiFont
                                        font.pixelSize: 8
                                    }
                                }
                                Text {
                                    objectName: "routeCellDamage"
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: host.routeCellDamage(ctx, modelData.index)
                                    color: {
                                        var text = String(host.routeCellDamage(ctx, modelData.index))
                                        if (text.indexOf("打不了") >= 0)
                                            return Theme.danger
                                        if (text.indexOf("没数值") >= 0)
                                            return Theme.ink3
                                        return Theme.ink
                                    }
                                    font.family: Theme.monoFont
                                    font.pixelSize: 10
                                }
                            }
                        }
                    }

                    // 链尾「计算」（和伤害计算一样：算完就藏，合计/剩血在底栏）
                    FlatBtn {
                        objectName: "routeRun"
                        visible: !host.routeComputed(ctx)
                        height: 26
                        label: "计算"
                        onClicked: host.routeCompute(ctx)
                    }
                }
            }
        }

        // ---- 底栏：总掉血 + 剩血 + 删掉 + 计算 ----
        // ---- 总掉血 / 剩血（钉在链右边，和伤害计算一样；没算不占地方） ----
        Column {
            objectName: "routeTotal"
            x: routeFlick.x + routeFlick.width - 88
            y: routeFlick.y
            width: 84
            spacing: 1
            visible: host.routeComputed(ctx)
            Text {
                objectName: "routeTotalDamage"
                width: parent.width
                horizontalAlignment: Text.AlignRight
                text: host.routeTotal(ctx)
                color: host.routeDead(ctx) ? Theme.danger : Theme.ink
                font.family: Theme.monoFont
                font.pixelSize: 10
                font.bold: true
            }
            Text {
                objectName: "routeLeftHp"
                width: parent.width
                horizontalAlignment: Text.AlignRight
                text: host.routeLeft(ctx)
                color: host.routeDead(ctx) ? Theme.danger : Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 8
            }
        }

        // ---- 拉大小的手柄（四边 + 四角，右下角那三道斜线是"拉这里"）----
        RouteGrip {
            objectName: "routeGripTL"
            pullLeft: true; pullTop: true
            anchors.left: parent.left; anchors.top: parent.top
            width: 12; height: 12
        }
        RouteGrip {
            objectName: "routeGripTR"
            pullRight: true; pullTop: true
            anchors.right: parent.right; anchors.top: parent.top
            width: 12; height: 12
        }
        RouteGrip {
            objectName: "routeGripBL"
            pullLeft: true; pullBottom: true
            anchors.left: parent.left; anchors.bottom: parent.bottom
            width: 12; height: 12
        }
        RouteGrip {
            objectName: "routeGrip"
            pullRight: true; pullBottom: true; marks: true
            anchors.right: parent.right; anchors.bottom: parent.bottom
            width: 18; height: 18
        }
        RouteGrip {
            objectName: "routeGripL"; pullLeft: true
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 5; height: Math.max(1, parent.height - 26)
        }
        RouteGrip {
            objectName: "routeGripR"; pullRight: true
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 5; height: Math.max(1, parent.height - 26)
        }
        RouteGrip {
            objectName: "routeGripT"; pullTop: true
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            height: 5; width: Math.max(1, parent.width - 26)
        }
        RouteGrip {
            objectName: "routeGripB"; pullBottom: true
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            height: 5; width: Math.max(1, parent.width - 26)
        }
    }

    // ---- 点格子填内容的下拉（「换」的时候用，同一扇窗的覆盖层） ----
    PickMenu { id: routeMenuLayer; host: routeWin.host; ctx: routeWin.ctx }

    // ---- 点缩略图改参数（和伤害计算同一个卡片） ----
    EditCard { host: routeWin.host; ctx: routeWin.ctx }
}
