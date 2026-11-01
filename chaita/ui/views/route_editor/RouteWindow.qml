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
// 它是**一扇真窗口**（无边框 + Qt.Tool，置顶跟着主窗口开关，和伤害计算同一个形状），能摆在
// 游戏旁边边看边走。状态都在主窗口的 `route*` 上，这里读 `host.xxx`。
Window {
    id: routeWin
    // 主窗口（共享工具 + controller 都在它身上）
    property var host
    // 这一扇窗自己的上下文（floor/index/cells/结果/菜单/编辑），多开各管各的
    property var ctx: ({})
    // 拉过的窗口大小：必须是 QML 属性，拖拽时改它才会触发宽高绑定重算
    property real winW: 0
    property real winH: 0

    // Ctrl+C 复制路线（和按钮「复制」同一件事，写系统剪贴板）
    Shortcut {
        sequence: "Ctrl+C"
        onActivated: host.routeCopy(ctx)
    }

    objectName: "routeWindow"
    visible: false
    color: "transparent"
    // 置顶跟着主窗口的「置顶」开关走（切换那一下 Qt 会重建这扇窗的原生窗口）。
    // 不用 transientParent 挂在主窗口名下：从属窗口拿不到键盘焦点，输入框打不了字。
    flags: Qt.FramelessWindowHint | Qt.Tool
           | (host && host.pinned ? Qt.WindowStaysOnTopHint : 0)

    readonly property var screenRect: {
        var scr = routeWin.screen
        if (!scr)
            return Qt.rect(0, 0, 1920, 1080)
        var originX = scr.virtualX !== undefined ? scr.virtualX : 0
        var originY = scr.virtualY !== undefined ? scr.virtualY : 0
        return Qt.rect(originX, originY, scr.width, scr.height)
    }
    // 窗口最外圈留给投影的透明边；灰底卡片（cardBox）画在它里面，和主窗口同一套
    readonly property int inset: Theme.windowInset
    // 灰底卡片里自上而下：标题行 34 → 人物一行 20 → 链那张白卡（8 间隔 + 8 内边距）
    readonly property int titleH: 34
    readonly property int heroLineH: 20
    readonly property int chainTop: titleH + heroLineH + 4 + 8
    readonly property int chainBottom: 16
    readonly property int autoW: 420
    readonly property int autoH: 2 * inset + chainTop + chainBottom
        + Math.min(300, Math.max(38, chainCol.implicitHeight))
    readonly property int maxH: Math.max(170, screenRect.height - 72)
    // 点开格子菜单时窗口长高一截（菜单挂在格子下面，得放得下）；拉过就按拉的来
    readonly property int autoHeight: Math.min(maxH, autoH
        + (ctx.menu !== "" ? 210 : 0))

    // 用户："路线图的窗口不能拉伸" —— 宽高都能拉（和伤害计算同一套手柄）
    width: Math.max(320, routeWin.winW > 0 ? routeWin.winW : autoW)
    height: Math.max(170, routeWin.winH > 0 ? routeWin.winH : autoHeight)

    // 整块钳在屏幕里（拖抬头以后不会掉出去）；卡片贴屏幕边就算到头，
    // 外圈 10px 透明投影边可以伸出屏幕
    function clampPos() {
        var rect = routeWin.screenRect
        if (!rect)
            return
        var left = rect.x + 2 - routeWin.inset
        var top = rect.y + 2 - routeWin.inset
        var right = Math.max(left, rect.x + rect.width - routeWin.width - 2
                                   + routeWin.inset)
        var bottom = Math.max(top, rect.y + rect.height - routeWin.height - 2
                                   + routeWin.inset)
        routeWin.x = Math.round(Math.max(left, Math.min(routeWin.x, right)))
        routeWin.y = Math.round(Math.max(top, Math.min(routeWin.y, bottom)))
    }

    // 开窗时摆在主窗口右边（和伤害计算同一个落点规矩：两张卡片之间留 8px）
    function place() {
        var rect = routeWin.screenRect
        if (!rect)
            return
        routeWin.x = Math.round(Math.max(
            rect.x + 4,
            Math.min(host.x + host.width + 8 - 2 * routeWin.inset,
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
    // routeWin.winW/H —— 窗口宽高是绑定出来的，不记的话绑定会把它顶回去。
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
                routeWin.winW = Math.round(w)
                routeWin.winH = Math.round(h)
                routeWin.x = Math.round(x)
                routeWin.y = Math.round(y)
                routeWin.clampPos()
            }
        }
    }

    // 窗口投影：和主窗口同一套（灰底卡片 + 软阴影）
    WindowShadow {
        anchors.fill: cardBox
        radius: cardBox.radius
    }

    Rectangle {
        id: cardBox
        objectName: "routeCard"
        anchors.fill: parent
        anchors.margins: routeWin.inset
        radius: 10
        color: Theme.canvas
        clip: true
        MouseArea { anchors.fill: parent }

        // ---- 抬头：拖着走 + 关 ----
        Item {
            id: routeHeader
            x: 8
            y: 0
            width: parent.width - 16
            height: routeWin.titleH
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
                id: routeTitle
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: "路线链"
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 14
                font.bold: true
            }
            Text {
                objectName: "routeFloorLabel"
                anchors.left: routeTitle.right
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: ctx.floor
                color: Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 11
                elide: Text.ElideRight
                width: Math.min(implicitWidth, 90)
            }
            IconBtn {
                id: routeClose
                objectName: "routeClose"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                glyph: "✕"
                glyphSize: 12
                hoverInk: Theme.danger
                hoverBack: Theme.dangerSoft
                onClicked: host.closeRoute(ctx)
            }
            TextBtn {
                id: routeDeleteText
                objectName: "routeDelete"
                pill: true
                anchors.right: routeClose.left
                anchors.rightMargin: 2
                anchors.verticalCenter: parent.verticalCenter
                text: "删"
                accent: Theme.danger
                onClicked: host.routeRemove(ctx)
            }
            TextBtn {
                id: routeCopyText
                objectName: "routeCopy"
                pill: true
                anchors.right: routeDeleteText.left
                anchors.rightMargin: 2
                anchors.verticalCenter: parent.verticalCenter
                text: "复制"
                accent: Theme.amber
                onClicked: host.routeCopy(ctx)
            }
            // 拖拽入口：按住「拖」把这条路线拖到「路线对比」窗口上松手
            // （要在按下那一下就起拖，所以不用 TextBtn 的 clicked）
            Rectangle {
                id: routeDragOutPill
                objectName: "routeDragOut"
                anchors.right: routeCopyText.left
                anchors.rightMargin: 2
                anchors.verticalCenter: parent.verticalCenter
                width: dragOutText.implicitWidth + 16
                height: 22
                radius: Theme.radius
                color: dragOutMouse.containsMouse ? Theme.hover : "transparent"
                Text {
                    id: dragOutText
                    anchors.centerIn: parent
                    text: "拖"
                    color: dragOutMouse.containsMouse ? Theme.amber : Theme.ink2
                    font.family: Theme.uiFont
                    font.pixelSize: 11
                }
                MouseArea {
                    id: dragOutMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.OpenHandCursor
                    onPressed: function (m) {
                        var text = host.routeStepsJson(ctx)
                        if (text === "")
                            return
                        dragOutChip.Drag.mimeData = {
                            "application/x-route-json": text }
                        dragOutChip.visible = true
                        dragOutChip.Drag.active = true
                    }
                }
            }

            // 拖动时跟着光标的小牌子
            Item {
                id: dragOutChip
                visible: false
                z: 40
                width: 56
                height: 20
                Drag.dragType: Drag.Automatic
                Drag.hotSpot: Qt.point(10, 10)
                Drag.onDragFinished: dragOutChip.visible = false
                Rectangle {
                    anchors.fill: parent
                    radius: 4
                    color: Theme.amber
                    Text {
                        anchors.centerIn: parent
                        text: "路线"
                        color: Theme.paperHi
                        font.family: Theme.uiFont
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
            }
        }

        // ---- 用哪个人物在算：血/攻/防/魔防（状态行读到的，打开/计算时刷新） ----
        Text {
            id: routeHeroLine
            objectName: "routeHeroLine"
            x: 12
            y: routeWin.titleH
            width: parent.width - 24
            height: routeWin.heroLineH
            verticalAlignment: Text.AlignVCenter
            text: "血 " + host.fmt(ctx.hero.hp)
                  + "  ·  攻 " + host.fmt(ctx.hero.atk)
                  + "  ·  防 " + host.fmt(ctx.hero.def)
                  + "  ·  魔防 " + host.fmt(ctx.hero.mdef)
            color: Theme.ink2
            font.family: Theme.uiFont
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        // 链那张白卡（里面是滚动区）
        Card {
            x: 8
            y: routeWin.chainTop - 8
            width: parent.width - 16
            height: routeFlick.height + 16
        }

        // ---- 链：勇者 → 格1,1 → 格1,2 …（摆不下折行） ----
        Flickable {
            id: routeFlick
            objectName: "routeFlick"
            x: 16
            y: routeWin.chainTop
            width: parent.width - 32
            height: Math.max(38, cardBox.height - routeWin.chainTop
                                 - routeWin.chainBottom)
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
                    font.pixelSize: 11
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
                            font.pixelSize: 10
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
                                        font.pixelSize: 10
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
                                    font.pixelSize: 11
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
                font.pixelSize: 11
                font.bold: true
            }
            Text {
                objectName: "routeLeftHp"
                width: parent.width
                horizontalAlignment: Text.AlignRight
                text: host.routeLeft(ctx)
                color: host.routeDead(ctx) ? Theme.danger : Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 10
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

    // 两层覆盖层（格子菜单 / 改参数卡片）只盖灰底卡片那一块，不盖外圈的投影边；
    // 菜单坐标（ctx.menuX/Y）也是按这一块算的
    Item {
        anchors.fill: parent
        anchors.margins: routeWin.inset

        // ---- 点格子填内容的下拉（「换」的时候用，同一扇窗的覆盖层） ----
        PickMenu { id: routeMenuLayer; host: routeWin.host; ctx: routeWin.ctx }

        // ---- 点缩略图改参数（和伤害计算同一个卡片） ----
        EditCard { host: routeWin.host; ctx: routeWin.ctx }
    }
}
