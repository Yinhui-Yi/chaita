import QtQuick
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 伤害计算（独立窗口）。状态在主窗口的 battle* 上，host 就是主窗口。
import QtQuick.Controls.Basic
import QtQuick.Window
// 按钮在上一层：shared/FlatBtn.qml
import "../shared"
// 它自己的下拉菜单（一个界面一个文件夹）
import "pick_menu"
// 它自己的覆盖层（一个界面一个文件夹）
import "edit_card"

// 伤害计算（另一扇独立窗口：无边框 + Qt.Tool，置顶跟着主窗口开关，能摆在游戏旁边）。
//
// 从 MainWindow.qml 搬出来的第一块（2026-10-28）。为什么搬：主界面那份 7000+ 行，
// 不同东西要各自一份文件。搬的代价只有一个 —— 它原来直接读主窗口的属性和函数
// （`win.battleRows` / `win.iconBase` / `win.fmt` …），现在都走 `host.xxx`，
// `host` 由创建方递进来（见 MainWindow.qml 的 `BattleWindow { host: win }`）。
//
// 这里只有界面：公式在 `chaita/game/battle.py`（纯函数、有单元测试），
// 状态（几行计划、每一步参数）在主窗口的 `win.battle*` 里，这一份只负责画和点。
Window {
    id: battleWin
    // 主窗口（原来直接叫 win）
    property var host

    // Ctrl+V 粘贴路线（和按钮「粘贴」同一件事，读系统剪贴板）
    Shortcut {
        sequence: "Ctrl+V"
        onActivated: host.battlePaste()
    }

    // 资源缩略图左下角的小字：这颗宝石加什么，用颜色分属性
    // （用户 2026-10-28："红宝石左下角是红色字体的攻击，蓝宝石是蓝色字体的防御，
    //   黄宝石从上到下是绿色的魔防、红色的攻击、蓝色的防御"）
    // 所以顺序写死成 魔防 → 攻击 → 防御；单属性就只有那一条。
    readonly property var markOrder: ["魔防", "攻击", "防御"]

    function markColor(word) {
        if (word === "攻击")
            return Theme.markAtk
        if (word === "防御")
            return Theme.markDef
        if (word === "魔防")
            return Theme.markMdef
        return Theme.ink3
    }

    // 一个效果里有哪些属性（按"魔防 / 攻击 / 防御"的顺序给出来）
    function effectMarks(effect) {
        var parts = controller
                ? controller.itemEffectPartList(String(effect || "")) : []
        var out = []
        for (var want = 0; want < battleWin.markOrder.length; want++) {
            var word = battleWin.markOrder[want]
            for (var i = 0; i < parts.length; i++) {
                if (String((parts[i] || {}).label || "").indexOf(word) === 0) {
                    out.push({ "text": word, "color": battleWin.markColor(word) })
                    break
                }
            }
        }
        return out
    }

    objectName: "battleWindow"
    visible: false
    color: "transparent"
    // 置顶跟着主窗口的「置顶」开关走（切换那一下 Qt 会重建这扇窗的原生窗口）。
    // 不用 transientParent 挂在主窗口名下：从属窗口拿不到键盘焦点，输入框打不了字。
    flags: Qt.FramelessWindowHint | Qt.Tool
           | (host && host.pinned ? Qt.WindowStaysOnTopHint : 0)
    readonly property var screenRect: {
        var scr = battleWin.screen
        if (!scr)
            return Qt.rect(0, 0, 1920, 1080)
        var originX = scr.virtualX !== undefined ? scr.virtualX : 0
        var originY = scr.virtualY !== undefined ? scr.virtualY : 0
        return Qt.rect(originX, originY, scr.width, scr.height)
    }
    readonly property int maxH: Math.max(320, screenRect.height - 72)
    readonly property int autoW: 430
    // 窗口最外圈留给投影的透明边；灰底卡片（battleCard）画在它里面，和主窗口同一套
    readonly property int inset: Theme.windowInset
    // 灰底卡片里自上而下：标题行 34 → 人物卡 44 → 按钮行（8 间隔 + 24）→
    // 链那张白卡（8 间隔 + 8 内边距）；底部留 38 给"没算进去的技能"那行小字
    // （白卡的 8 内边距 + 8 间隔 + 一行小字 14）
    readonly property int headH: 34
    readonly property int heroH: 44
    readonly property int btnTop: headH + heroH + 8
    readonly property int chainTop: btnTop + 24 + 8 + 8
    readonly property int chainBottom: 8 + 8 + 14 + 8
    // 还没被用户拉过时按内容撑高（链折行以后内容会更高，窗口跟着长）
    readonly property int autoH: 2 * inset + chainTop + chainBottom
        + Math.max(host.battleRowH,
                   Math.min(320, battleCol.implicitHeight))
    // 用户："伤害计算界面怎么不能拉伸窗口" —— 宽高都能拉（见下面的
    // BattleGrip）；拉过就按拉过的来，不再跟内容自适应
    width: Math.max(320, host.battleWinW > 0 ? host.battleWinW : autoW)
    height: Math.max(200, Math.min(maxH, host.battleWinH > 0
                                        ? host.battleWinH : autoH))
    // 整块钳在屏幕里（拖抬头/改大小以后不会掉出去）；卡片贴屏幕边就算到头，
    // 外圈 10px 透明投影边可以伸出屏幕
    function clampPos() {
        var rect = battleWin.screenRect
        if (!rect)
            return
        var left = rect.x + 2 - battleWin.inset
        var top = rect.y + 2 - battleWin.inset
        var right = Math.max(left, rect.x + rect.width - battleWin.width - 2
                                   + battleWin.inset)
        var bottom = Math.max(top, rect.y + rect.height - battleWin.height - 2
                                   + battleWin.inset)
        battleWin.x = Math.round(Math.max(left, Math.min(battleWin.x, right)))
        battleWin.y = Math.round(Math.max(top, Math.min(battleWin.y, bottom)))
    }
    // 摆在主窗口右边：两张卡片之间留 8px（两边各自还有一圈投影边）
    function place() {
        var rect = battleWin.screenRect
        if (!rect)
            return
        battleWin.x = Math.round(Math.max(
            rect.x + 4,
            Math.min(host.x + host.width + 8 - 2 * battleWin.inset,
                     rect.x + rect.width - battleWin.width - 12)))
        battleWin.y = Math.round(Math.max(
            rect.y + 4,
            Math.min(host.y + 60,
                     rect.y + rect.height - battleWin.height - 12)))
    }
    // 问号菜单挂在那一行下面。链会折行，行高是内容撑出来的，
    // 所以位置不能再用"第几行 × 行高"算：直接把那一行的坐标换算过来
    // （行在 Flickable 里，mapToItem 会带上 contentY）。
    function battleRowItem(planIndex) {
        var list = battleCol.children
        for (var i = 0; i < list.length; i++) {
            var child = list[i]
            if (child.objectName === "battleRow"
                    && child.planIndex === planIndex)
                return child
        }
        return null
    }
    function placeMenu() {
        if (host.battleMenu === "" || host.battleMenuPlan < 0)
            return
        var row = battleRowItem(host.battleMenuPlan)
        if (!row)
            return
        var menuH = 56 + Math.min(
            Math.max(96, Math.min(240, battleFlick.height - 40)),
            Math.max(1, host.battleMenuRows) * 26) + 8
        var rowTop = row.mapToItem(battleCard, 0, 0).y
        var top = rowTop + row.height + 2
        if (top + menuH > battleCard.height - 4)
            top = Math.max(4, rowTop - menuH - 2)
        host.battleMenuX = 30
        host.battleMenuY = top
    }
    Shortcut {
        sequence: "Esc"
        onActivated: host.closeBattle()
    }
    onActiveChanged: {
        if (!battleWin.active)
            host.battleMenu = ""
    }
    // 读取线程回来（状态行更新）→ 把人物数值填进来
    // （用户："不能读取当前状态"）
    Connections {
        target: controller
        function onStatusTextChanged() {
            if (host.battleWindow)
                host.battlePullHero()
        }
    }

    // ---- 拉大小：四条边 + 四个角都能拉 ----
    // 用户："伤害计算界面怎么不能拉伸窗口"。和「这一层」小窗同一套算法
    // （SheetGrip）：位移必须用**屏幕坐标**；拉出来的尺寸要记进
    // host.battleWinW/H —— 窗口宽高是绑定出来的，不记的话绑定会把它顶回去。
    component BattleGrip: Item {
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
                color: gripMouse.containsMouse
                       ? host.accent : host.ink3
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
                           ? Qt.SizeFDiagCursor
                           : Qt.SizeBDiagCursor
                return horizontal ? Qt.SizeHorCursor
                                  : Qt.SizeVerCursor
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
                startX = battleWin.x
                startY = battleWin.y
                startW = battleWin.width
                startH = battleWin.height
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
                w = Math.max(320, Math.min(
                    battleWin.screenRect.width - 8, w))
                h = Math.max(200, Math.min(battleWin.maxH, h))
                // 从上边/左边拉：窗口原点跟着动，另一侧才不动
                var x = grip.pullLeft
                        ? startX + (startW - w) : startX
                var y = grip.pullTop
                        ? startY + (startH - h) : startY
                host.battleWinW = Math.round(w)
                host.battleWinH = Math.round(h)
                battleWin.x = Math.round(x)
                battleWin.y = Math.round(y)
                battleWin.clampPos()
            }
        }
    }

    // 窗口投影：和主窗口同一套（灰底卡片 + 软阴影）
    WindowShadow {
        anchors.fill: battleCard
        radius: battleCard.radius
    }

    Rectangle {
        id: battleCard
        anchors.fill: parent
        anchors.margins: battleWin.inset
        radius: 10
        color: Theme.canvas
        clip: true
        focus: true
        // Esc 关掉这一扇（Shortcut 要窗口是 active 才响，这里再兜一层）
        Keys.onEscapePressed: host.closeBattle()
        MouseArea { anchors.fill: parent }

        // ---- 抬头：拖着走 + 读取当前状态 + 关 ----
        Item {
            id: battleHeader
            x: 8
            y: 0
            width: parent.width - 16
            height: battleWin.headH

            // 用户："不能移动" —— 拖抬头挪窗口（和「这一层」同一种算法：
            // 用屏幕坐标，窗口跟着鼠标走不会漂）
            MouseArea {
                id: battleDrag
                objectName: "battleDrag"
                anchors.fill: parent
                property real pressX: 0
                property real pressY: 0
                property real startX: 0
                property real startY: 0
                cursorShape: pressed ? Qt.ClosedHandCursor
                                     : Qt.ArrowCursor
                onPressed: function (m) {
                    var at = mapToGlobal(m.x, m.y)
                    pressX = at.x
                    pressY = at.y
                    startX = battleWin.x
                    startY = battleWin.y
                }
                onPositionChanged: function (m) {
                    if (!pressed)
                        return
                    var at = mapToGlobal(m.x, m.y)
                    battleWin.x = Math.round(startX + (at.x - pressX))
                    battleWin.y = Math.round(startY + (at.y - pressY))
                    battleWin.clampPos()
                }
            }

            Text {
                id: battleTitle
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: "伤害计算"
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 14
                font.bold: true
            }
            Text {
                objectName: "battleHint"
                anchors.left: battleTitle.right
                anchors.leftMargin: 10
                anchors.right: battleRead.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: "点缩略图改数值 · 点箭头插入 · 点问号接着加"
                color: Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 11
                elide: Text.ElideRight
            }
            // 用户："不能读取当前状态" —— 就在这儿读一次人物面板
            FlatBtn {
                id: battleRead
                objectName: "battleRead"
                anchors.right: battleClose.left
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                label: controller && controller.updating ? "…" : "读取"
                onClicked: {
                    if (controller && !controller.updating)
                        controller.updateStatus()
                }
            }
            IconBtn {
                id: battleClose
                objectName: "battleClose"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                glyph: "✕"
                glyphSize: 12
                hoverInk: Theme.danger
                hoverBack: Theme.dangerSoft
                onClicked: host.closeBattle()
            }
        }

        // ---- 人物状态：血 / 攻 / 防 / 魔防（状态行带出来，可改） ----
        // 用户："血攻防魔防怎么不像状态一样显示" —— 和主窗口状态行同一套
        // 写法：一个图标挨着一个数（这里的数能改，点进去有白底和蓝框）
        Card {
            id: battleHeroCard
            x: 8
            y: battleWin.headH
            width: parent.width - 16
            height: battleWin.heroH
            pad: 8
            Row {
                id: battleHeroRow
                objectName: "battleHeroRow"
                width: parent.width
                spacing: 6
                Repeater {
                    model: [["hp", "血"], ["atk", "攻"],
                            ["def", "防"], ["mdef", "魔防"]]
                    delegate: Rectangle {
                        id: heroCell
                        objectName: "battleHero_" + modelData[0]
                        width: (battleHeroRow.width - 3 * battleHeroRow.spacing) / 4
                        height: 28
                        radius: 6
                        color: heroField.activeFocus ? Theme.paper : Theme.tile
                        border.width: 1
                        border.color: heroField.activeFocus
                                      ? Theme.accent : "transparent"
                        Image {
                            id: heroIcon
                            x: 8
                            width: 14
                            height: 14
                            anchors.verticalCenter: parent.verticalCenter
                            source: host.iconBase && modelData[0] !== ""
                                    ? host.iconBase + modelData[0] + ".png"
                                    : ""
                            visible: source !== ""
                            smooth: false
                        }
                        // 没配素材目录时退回一个字，位置不跳
                        Text {
                            x: 8
                            anchors.verticalCenter: parent.verticalCenter
                            visible: !heroIcon.visible
                            text: modelData[1]
                            color: Theme.ink3
                            font.family: Theme.uiFont
                            font.pixelSize: 11
                        }
                        TextField {
                            id: heroField
                            objectName: "battleHero_" + modelData[0] + "Field"
                            anchors.left: parent.left
                            anchors.leftMargin: 26
                            anchors.right: parent.right
                            anchors.rightMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            height: 22
                            verticalAlignment: TextInput.AlignVCenter
                            background: null
                            padding: 0
                            leftPadding: 2
                            rightPadding: 2
                            topPadding: 0
                            bottomPadding: 0
                            color: Theme.ink
                            font.family: Theme.monoFont
                            font.pixelSize: 12
                            selectByMouse: true
                            text: String(Number((host.battleHero || {})[modelData[0]] || 0))
                            // 边改边算（不用等回车，看着数字变最直观）。
                            // 只认数字，而且值没变就别写回去 —— 不然
                            // 绑定循环（text ← battleHero ← text）
                            onTextChanged: {
                                var clean = String(text).replace(/[^0-9]/g, "")
                                if (clean !== String(text)) {
                                    text = clean
                                    return
                                }
                                var now = clean === "" ? 0 : Number(clean)
                                if (now !== Number((host.battleHero || {})[modelData[0]] || 0))
                                    host.battleSetHero(modelData[0], clean)
                            }
                        }
                    }
                }
            }
        }

        // ---- 加一行计算（用户："一个按钮创建新的计算"）----
        Row {
            id: battleBtnRow
            objectName: "battleBtnRow"
            x: 8
            y: battleWin.btnTop
            width: parent.width - 16
            height: Theme.controlH
            spacing: 6
            FlatBtn {
                id: battleAddRow
                objectName: "battleAddRow"
                label: "＋ 新的计算"
                onClicked: host.battleAddPlan()
            }
            FlatBtn {
                id: battlePaste
                objectName: "battlePaste"
                label: "粘贴"
                onClicked: host.battlePaste()
            }
            // 弹簧：把「清空」顶到右边（宽度按实际按钮算，别写死数字）
            Item {
                width: Math.max(0, battleBtnRow.width - battleAddRow.width
                                   - battlePaste.width
                                   - battleClearBtn.width
                                   - 2 * battleBtnRow.spacing)
                height: 1
            }
            FlatBtn {
                id: battleClearBtn
                objectName: "battleClear"
                label: "清空"
                onClicked: host.battleClear()
            }
        }

        // ---- 一行一次计算：勇者 → 怪 −930 → 宝石 → 怪 −2万 … ----
        // 用户："一行！！！"：一次计算就是一整行（横向一条链），
        // 掉血写在每个怪后面；开几行不同顺序的，右边总掉血对着比。
        // ---- 一行一次计算：勇者 → 怪 (−930) → 宝石 → 怪 (−300) … ----
        // 用户："一行！！！"：一次计算就是一整行；"我加的怪和资源一多就该
        // 换行" —— 一条链是 Flow，摆不下自动折到下一行，行高跟着长。
        // 掉血写在每个怪后面（加括号），右边钉着这一行的总掉血。
        // 链那张白卡（里面是滚动区）
        Card {
            x: 8
            y: battleWin.btnTop + Theme.controlH + 8
            width: parent.width - 16
            height: battleFlick.height + 16
        }
        Flickable {
            id: battleFlick
            objectName: "battleFlick"
            x: 16
            y: battleWin.chainTop
            width: parent.width - 32
            height: Math.max(host.battleRowH,
                             battleCard.height - battleWin.chainTop
                             - battleWin.chainBottom)
            contentWidth: width
            contentHeight: battleCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // 滚动了，问号菜单要跟着那一行走
            onContentYChanged: host.battleMenuPlace()

            Column {
                id: battleCol
                width: battleFlick.width
                spacing: host.battleRowGap

                Text {
                    objectName: "battleEmpty"
                    width: battleCol.width
                    height: 30
                    visible: host.battleRows.length === 0
                    text: "点上面的「＋ 新的计算」，再点那一行的问号选怪或资源。"
                    color: host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                    verticalAlignment: Text.AlignVCenter
                }

                Repeater {
                    model: host.battleRows
                    delegate: Item {
                        id: planRow
                        objectName: "battleRow"
                        width: battleCol.width
                        // 链折行了这一行就更高（不是固定 26）
                        height: Math.max(host.battleRowH,
                                         chainFlow.height + 2)

                        readonly property var plan: modelData || ({})
                        readonly property int planIndex:
                            plan.index === undefined
                            ? -1 : Number(plan.index)
                        readonly property var steps: plan.steps || []
                        readonly property bool best:
                            host.battleRows.length > 1
                            && host.battleBestPlan === planIndex

                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: best ? Theme.tile : "transparent"
                        }

                        // 这一行的链：摆不下就折行（用户："一多就该换行"）
                        Flow {
                            id: chainFlow
                            objectName: "battleChain"
                            x: 3
                            y: 1
                            width: Math.max(1, planRow.width - 100)
                            spacing: 3

                            // 开头永远是勇者
                            Item {
                                objectName: "battleRowHero"
                                width: 16
                                height: host.battleRowH
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
                                    color: host.ink2
                                    font.family: host.uiFont
                                    font.pixelSize: 10
                                }
                            }

                            // 走一步：箭头 + 那一格 + 结果。一步整体不拆行。
                            // 点箭头 = 在这一格前面插一个（用户："点箭头要能插入"）
                            Repeater {
                                model: steps
                                delegate: Item {
                                    objectName: "battleStep"
                                    width: stepRow.implicitWidth
                                    height: host.battleRowH
                                    Row {
                                        id: stepRow
                                        spacing: 3
                                        anchors.verticalCenter: parent.verticalCenter
                                        ChainArrow {
                                            objectName: "battleRowArrow"
                                            onClicked: host.openBattleMenu(
                                                plan.index, index)
                                        }
                                        Item {
                                            objectName: "battleRowIcon"
                                            width: host.battleSlotW
                                            height: host.battleSlotW
                                            anchors.verticalCenter: parent.verticalCenter
                                            Image {
                                                anchors.fill: parent
                                                source: host.battleStepIcon(modelData)
                                                visible: source !== ""
                                                fillMode: Image.PreserveAspectFit
                                                smooth: false
                                            }
                                            Text {
                                                anchors.centerIn: parent
                                                visible: !host.hasUrl(
                                                    host.battleStepIcon(modelData))
                                                text: String(modelData.kind || "")
                                                      === "item" ? "物" : "怪"
                                                color: host.ink3
                                                font.family: host.uiFont
                                                font.pixelSize: 10
                                            }
                                            // 点这一格 = 改它的数值
                                            MouseArea {
                                                anchors.fill: parent
                                                anchors.margins: -3
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: host.battleEditStep(
                                                    plan.index, index)
                                            }
                                        }
                                        // 这颗资源加什么：紧挨缩略图写，颜色分属性
                                        // （红=攻击、蓝=防御、绿=魔防；黄宝石三样从上到下）。
                                        // 缩略图只有 14，三个字塞不进图里 —— 写在图右边，
                                        // 那里本来就空着（资源那格没有掉血数）。
                                        Column {
                                            objectName: "battleStepMarks"
                                            anchors.verticalCenter: parent.verticalCenter
                                            spacing: 0
                                            Repeater {
                                                model: String(modelData.kind || "")
                                                       === "item"
                                                       ? battleWin.effectMarks(
                                                             modelData.effect)
                                                       : []
                                                delegate: Text {
                                                    objectName: "battleStepMark"
                                                    text: modelData.text
                                                    color: modelData.color
                                                    font.family: Theme.uiFont
                                                    font.pixelSize: 8
                                                    font.bold: true
                                                }
                                            }
                                        }
                                        // 掉血写在怪后面、加括号
                                        // （用户："伤害外面要加括号"）；
                                        // 资源那格什么都不写（只要缩略图）
                                        Text {
                                            objectName: "battleRowDamage"
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: {
                                                if (!host.battlePlanComputed(plan.index))
                                                    return String(modelData.kind || "")
                                                           === "item" ? "" : "—"
                                                var row = host.battleStepResult(
                                                    plan.index, index)
                                                if (String(modelData.kind || "") === "item")
                                                    return ""
                                                if (row.ok === false)
                                                    return "（打不了）"
                                                if (row.lethal)
                                                    return "（−" + host.fmt(row.damage)
                                                           + "）打不过"
                                                if (row.ok)
                                                    return "（−" + host.fmt(row.damage) + "）"
                                                return "—"
                                            }
                                            color: {
                                                if (!host.battlePlanComputed(plan.index))
                                                    return host.ink3
                                                var row = host.battleStepResult(
                                                    plan.index, index)
                                                return (row.ok === false || row.lethal)
                                                       ? host.danger : host.ink
                                            }
                                            font.family: host.monoFont
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }

                            // 链尾的箭头 + 问号（接着往这一行加）
                            // 再往后是这一行自己的「计算」
                            // （用户："计算按钮要在每一条后面"
                            // + "每一条要能单独计算"）
                            Item {
                                objectName: "battleRowEnd"
                                width: endRow.implicitWidth
                                height: host.battleRowH
                                Row {
                                    id: endRow
                                    spacing: 3
                                    anchors.verticalCenter: parent.verticalCenter
                                    ChainArrow {
                                        objectName: "battleRowArrowEnd"
                                        onClicked: host.openBattleMenu(
                                            plan.index, -1)
                                    }
                                    Rectangle {
                                        objectName: "battleRowAsk"
                                        width: host.battleAskW
                                        height: host.battleAskW
                                        anchors.verticalCenter: parent.verticalCenter
                                        radius: 4
                                        color: askMouse.containsMouse
                                               ? host.paperLo : "transparent"
                                        border.width: 1
                                        border.color: askMouse.containsMouse
                                                      ? host.accent : host.ink3
                                        Text {
                                            anchors.centerIn: parent
                                            text: "?"
                                            color: askMouse.containsMouse
                                                   ? host.accent : host.ink3
                                            font.family: host.uiFont
                                            font.pixelSize: 11
                                        }
                                        MouseArea {
                                            id: askMouse
                                            anchors.fill: parent
                                            anchors.margins: -2
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: host.openBattleMenu(
                                                plan.index)
                                        }
                                    }
                                    FlatBtn {
                                        objectName: "battlePlanRun"
                                        visible: !host.battlePlanComputed(plan.index)
                                        label: "计算"
                                        onClicked: host.battleComputePlan(plan.index)
                                    }
                                }
                            }
                        }

                        // 这一行的合计（钉在右边：几行摆一起就能比）
                        Item {
                            objectName: "battlePlanTotal"
                            x: planRow.width - 96
                            y: 0
                            width: 78
                            height: planRow.height

                            Column {
                                width: parent.width
                                spacing: 0
                                anchors.verticalCenter: parent.verticalCenter
                                visible: host.battlePlanComputed(plan.index)
                                Text {
                                    objectName: "battlePlanDamage"
                                    width: parent.width
                                    horizontalAlignment: Text.AlignRight
                                    text: host.battlePlanTotal(plan.index)
                                    color: best ? host.accent : host.ink
                                    font.family: host.monoFont
                                    font.pixelSize: 11
                                    font.bold: best
                                }
                                Text {
                                    objectName: "battlePlanLeftHp"
                                    width: parent.width
                                    horizontalAlignment: Text.AlignRight
                                    text: host.battlePlanLeft(plan.index)
                                    color: host.ink3
                                    font.family: host.uiFont
                                    font.pixelSize: 10
                                }
                            }
                        }

                        // 删掉这一行
                        Text {
                            objectName: "battleRowDelete"
                            anchors.right: parent.right
                            anchors.rightMargin: 0
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14
                            height: 16
                            horizontalAlignment: Text.AlignHCenter
                            text: "✕"
                            opacity: deleteMouse.containsMouse ? 1 : 0.4
                            color: deleteMouse.containsMouse
                                   ? host.danger : host.ink3
                            font.pixelSize: 11
                            MouseArea {
                                id: deleteMouse
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: host.battleRemovePlan(plan.index)
                            }
                        }
                    }
                }
            }
        }

        // ---- 没算进去的技能（薄薄一行小字，底栏的大黄块已经删了） ----
        Text {
            objectName: "battleUnhandled"
            x: 12
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            width: parent.width - 24
            visible: text !== ""
            text: {
                var plans = host.battlePlanResults || []
                var seen = []
                for (var i = 0; i < plans.length; i++) {
                    var list = (plans[i] || {}).unhandled || []
                    for (var j = 0; j < list.length; j++) {
                        if (seen.indexOf(list[j]) < 0)
                            seen.push(list[j])
                    }
                }
                if (seen.length === 0)
                    return ""
                return "这些技能没算进去：" + seen.join("；")
            }
            color: host.ink3
            font.family: host.uiFont
            font.pixelSize: 10
            elide: Text.ElideRight
        }

        // ---- 拉大小（用户："伤害计算界面怎么不能拉伸窗口"）----
        // 四条边 + 四个角都能拉，右下角那三道斜线是"拉这里"的标记
        BattleGrip {
            objectName: "battleGripTL"
            pullLeft: true; pullTop: true
            anchors.left: parent.left; anchors.top: parent.top
            width: 12; height: 12
        }
        BattleGrip {
            objectName: "battleGripTR"
            pullRight: true; pullTop: true
            anchors.right: parent.right; anchors.top: parent.top
            width: 12; height: 12
        }
        BattleGrip {
            objectName: "battleGripBL"
            pullLeft: true; pullBottom: true
            anchors.left: parent.left; anchors.bottom: parent.bottom
            width: 12; height: 12
        }
        BattleGrip {
            objectName: "battleGrip"
            pullRight: true; pullBottom: true; marks: true
            anchors.right: parent.right; anchors.bottom: parent.bottom
            width: 18; height: 18
        }
        BattleGrip {
            objectName: "battleGripL"; pullLeft: true
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 5; height: Math.max(1, parent.height - 26)
        }
        BattleGrip {
            objectName: "battleGripR"; pullRight: true
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 5; height: Math.max(1, parent.height - 26)
        }
        BattleGrip {
            objectName: "battleGripT"; pullTop: true
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            height: 5; width: Math.max(1, parent.width - 26)
        }
        BattleGrip {
            objectName: "battleGripB"; pullBottom: true
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            height: 5; width: Math.max(1, parent.width - 26)
        }
    }

    // 两层覆盖层（改参数卡片 / 问号菜单）只盖灰底卡片那一块，不盖外圈的投影边；
    // 菜单坐标（battleMenuX/Y）也是按这一块算的
    Item {
        anchors.fill: parent
        anchors.margins: battleWin.inset

        // ---- 点缩略图改参数（用户："点击缩略图可以修改参数"）----
        EditCard { host: battleWin.host }

        // ---- 问号的下拉菜单：怪 + 资源摆一个列表 ----
        // （用户："点问号选怪或资源"）
        PickMenu { host: battleWin.host }
    }
}
