import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 配色/按钮在上一层：views/shared
import "../shared"

// 加属性收益（独立窗口：无边框 + Qt.Tool，置顶跟着主窗口开关，能摆在游戏旁边）。
//
// 用户 2026-11-01："基于当前的属性计算，每增加 x 点攻击防御魔防，剩下的怪会减少多少
// 伤害：对于每一只怪 / 对于每一种（一只 × 数量）/ 对于剩下所有怪，需要可以配上界，
// 超过上界的按上界计算"，"三项各一个输入框 可以同时修改"、"上界封所有"，
// 并且强调"这是新功能！！！不要和之前的混在一起！！！"。
//
// **它接着的是清单那张怪表，不是一张新报表** —— 用户实际的动作是：
//   打完一层 → 清单里 ○ 的是还剩的怪 → 想加属性 → 打开它 → 每种后面直接写
//   "一只 X / 共 Y" → 点亮某一行，地图就切到那层、圈出那一格，直接去打。
// 所以每一行长得和「这一层」清单一样：**缩略图 + 名字 + 位置**（在这个软件里，
// 一只怪的身份证就是图和坐标，光有名字认不出是哪只）。
//
// 规矩：
//   · 剩下 = 各层清单里没勾掉（○）的怪；同层同名合并成一行 ×N。
//   · 一只 = 单只少掉多少；共 = 一只 × 剩下几只；合计 = 所有层相加。
//   · 上界只封**合计**（默认填当前血量：省下来的血不可能超过你有的血），
//     单只/单种照实写；封了就写清"本来多少"。
//   · 手册里没数值 / 打不动的怪照样列出来，写清"没算"，绝不编数字。
Window {
    id: gainWin
    // 主窗口（窗口开关、位置、四格输入、结果都在它身上）
    property var host

    objectName: "gainWindow"
    visible: false
    color: "transparent"
    // 置顶跟着主窗口的「置顶」开关走（切换那一下 Qt 会重建这扇窗的原生窗口）。
    // 不用 transientParent 挂在主窗口名下：从属窗口拿不到键盘焦点，输入框打不了字。
    flags: Qt.FramelessWindowHint | Qt.Tool
           | (host && host.pinned ? Qt.WindowStaysOnTopHint : 0)

    // ---- 四格输入 + 结果：都在主窗口（`host.gain*`），关掉再开还在 ----
    readonly property var result: host.gainResult || ({})
    readonly property var floors: (result || {}).floors || []
    readonly property var hero: (result || {}).hero || ({})

    // ---- 版式（灰底卡片里自上而下）：标题行 / 白卡：当前属性 / 输入 / 细线 / 列表 / 合计 ----
    // 窗口最外圈留给投影的透明边；灰底卡片（gainCard）画在它里面，和主窗口同一套
    readonly property int inset: Theme.windowInset
    readonly property int headerH: 34
    // 白卡左右各缩 8，卡里内容再缩 8：内容离灰底卡片边 16
    readonly property int heroY: headerH + 10
    readonly property int heroH: 18
    readonly property int inputY: heroY + heroH + 4
    readonly property int inputH: 24
    readonly property int hairY: inputY + inputH + 8
    readonly property int listY: hairY + 6
    readonly property int footerH: 32
    // 一行一种（缩略图 16 + 上下各 4） / 一行一个组头
    readonly property int speciesH: 24
    readonly property int groupH: 22
    // 左右内边距：整张卡片只有这一个数（别每行各写一个魔法数字）
    readonly property int padW: 16
    // 每行右边的四列（从右往左：共 / 一只 / ×数量 / 位置），两种行（算得出的、
    // 没数值的）共用这套宽度，才对得齐
    readonly property int allW: 60
    readonly property int oneW: 60
    readonly property int countW: 30
    readonly property int spotW: 84
    readonly property int colGap: 6

    readonly property var screenRect: {
        var scr = gainWin.screen
        if (!scr)
            return Qt.rect(0, 0, 1920, 1080)
        var originX = scr.virtualX !== undefined ? scr.virtualX : 0
        var originY = scr.virtualY !== undefined ? scr.virtualY : 0
        return Qt.rect(originX, originY, scr.width, scr.height)
    }
    readonly property int maxH: Math.max(200, screenRect.height - 72)
    readonly property int autoW: 2 * inset + 400
    readonly property int autoH: 2 * inset + listY + 6
        + Math.max(30, Math.min(320, gainCol.implicitHeight)) + footerH + 8

    width: Math.max(320, host.gainWinW > 0 ? host.gainWinW : autoW)
    height: Math.max(150, host.gainWinH > 0
                     ? host.gainWinH : Math.min(maxH, autoH))

    // 卡片贴屏幕边就算到头：外圈 10px 透明投影边可以伸出屏幕
    function clampPos() {
        var rect = gainWin.screenRect
        if (!rect)
            return
        var left = rect.x + 2 - gainWin.inset
        var top = rect.y + 2 - gainWin.inset
        var right = Math.max(left, rect.x + rect.width - gainWin.width - 2
                                   + gainWin.inset)
        var bottom = Math.max(top, rect.y + rect.height - gainWin.height - 2
                                   + gainWin.inset)
        gainWin.x = Math.round(Math.max(left, Math.min(gainWin.x, right)))
        gainWin.y = Math.round(Math.max(top, Math.min(gainWin.y, bottom)))
    }

    // 开窗时摆在主窗口右边；伤害计算 / 路线对比开着就排到它们右边（别叠在一起）
    // （两张卡片之间留 8px，两边各自还有一圈投影边）
    function place() {
        var rect = gainWin.screenRect
        if (!rect)
            return
        var gap = 8 - 2 * gainWin.inset
        var baseX = host.x + host.width + gap
        var others = [host.battleWindow, host.compareWindow]
        for (var i = 0; i < others.length; i++) {
            var other = others[i]
            if (other && other.visible)
                baseX = Math.max(baseX, other.x + other.width + gap)
        }
        gainWin.x = Math.round(Math.max(
            rect.x + 4,
            Math.min(baseX, rect.x + rect.width - gainWin.width - 12)))
        gainWin.y = Math.round(Math.max(
            rect.y + 4,
            Math.min(host.y + 60, rect.y + rect.height - gainWin.height - 12)))
    }

    // ---- 算：一律问 controller（公式在 game/battle.py，别在界面里重算）----
    function number(text) {
        var clean = String(text || "").replace(/[^0-9]/g, "")
        return clean === "" ? 0 : Number(clean)
    }

    // 四格的值都放在 host.gain* 上（`kind` = atk / def / mdef / cap）
    function gainValue(kind) {
        if (kind === "atk")
            return host.gainAtk
        if (kind === "def")
            return host.gainDef
        if (kind === "mdef")
            return host.gainMdef
        return host.gainCap
    }

    function setGainValue(kind, text) {
        if (kind === "atk")
            host.gainAtk = text
        else if (kind === "def")
            host.gainDef = text
        else if (kind === "mdef")
            host.gainMdef = text
        else
            host.gainCap = text
        gainWin.recalc()
    }

    function recalc() {
        if (!controller)
            return
        host.gainResult = controller.propertyGain(JSON.stringify({
            "gain": { "atk": gainWin.number(host.gainAtk),
                      "def": gainWin.number(host.gainDef),
                      "mdef": gainWin.number(host.gainMdef) },
            "cap": gainWin.number(host.gainCap) }))
    }

    // 当前属性那一行（点不了，就是从状态行读到的值）
    function heroText() {
        var got = gainWin.hero || ({})
        if (got.atk === undefined
                || (Number(got.hp || 0) === 0 && Number(got.atk || 0) === 0))
            return "还没读到人物数值：按导航条 ↻ 刷一次状态"
        return "当前 血 " + Number(got.hp || 0) + " · 攻 " + Number(got.atk || 0)
               + " · 防 " + Number(got.def || 0)
               + " · 魔防 " + Number(got.mdef || 0)
    }

    // 合计那一行：没填加成先说清怎么用；封顶了就说清"本来多少、按上界算"
    function totalText() {
        var got = gainWin.result || ({})
        if (got.total_saved === undefined || gainWin.floors.length === 0)
            return ""
        if (gainWin.typedGain === 0)
            return "左边填一个加成，这里算剩下的怪少掉多少血"
        var head = "剩下 " + Number(got.count_species || 0) + " 种 "
                   + Number(got.count_monsters || 0) + " 只 · 少掉 "
        if (got.capped)
            return head + Number(got.capped_saved || 0) + " 血（本来 "
                   + Number(got.total_saved || 0) + "，按上界 "
                   + Number(got.cap || 0) + "）"
        return head + Number(got.total_saved || 0) + " 血"
    }

    // 三格加成加起来是 0：还没填，别摆一排"少掉 0"
    readonly property int typedGain: number(host.gainAtk) + number(host.gainDef)
                                     + number(host.gainMdef)

    // 组头右边：这一层还剩几只 + 这一层一共少掉多少（算不了的不算在里面）
    // 还没填加成时只报"还剩几只"，别摆一排"少掉 0"
    function groupHeadText(floor) {
        var got = floor || ({})
        var species = got.species || []
        if (species.length === 0)
            return "没算"
        var heads = 0
        for (var i = 0; i < species.length; i++)
            heads += Number(species[i].count || 0)
        var head = species.length + " 种 " + heads + " 只"
        if (gainWin.typedGain === 0)
            return head
        return head + " · 少掉 " + Number(got.saved || 0)
    }

    // 这一种怪在图上哪几格（和「这一层」清单用同一处数据，坐标从 1 数）
    function spotText(spots) {
        var list = spots || []
        if (list.length === 0)
            return ""
        var parts = []
        for (var i = 0; i < list.length && i < 3; i++)
            parts.push((Number(list[i].row) + 1) + ","
                       + (Number(list[i].col) + 1))
        if (list.length > 3)
            parts.push("…")
        return parts.join(" ")
    }

    function spotsOf(floorText, name) {
        if (!host || !host.gridPositionsFor)
            return []
        return host.gridPositionsFor(floorText, name, "")
    }

    function iconOf(name) {
        if (!host || !host.monsterIconNamed)
            return ""
        return String(host.monsterIconNamed(name) || "")
    }

    Shortcut {
        sequence: "Esc"
        onActivated: host.closeGain()
    }

    // 清单/手册/状态一变就重算：开着窗边打边看，数字不该过期
    Connections {
        target: controller
        function onMapHistoryChanged() { gainWin.recalc() }
        function onMonstersChanged() { gainWin.recalc() }
        function onStatusTextChanged() { gainWin.recalc() }
    }

    // ---- 拉大小：四条边 + 四个角（和伤害计算/路线对比同一套算法）----
    component GainGrip: Item {
        id: grip
        property bool pullLeft: false
        property bool pullRight: false
        property bool pullTop: false
        property bool pullBottom: false

        MouseArea {
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
                startX = gainWin.x
                startY = gainWin.y
                startW = gainWin.width
                startH = gainWin.height
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
                w = Math.max(320, Math.min(gainWin.screenRect.width - 8, w))
                h = Math.max(150, Math.min(gainWin.maxH, h))
                var x = grip.pullLeft ? startX + (startW - w) : startX
                var y = grip.pullTop ? startY + (startH - h) : startY
                host.gainWinW = Math.round(w)
                host.gainWinH = Math.round(h)
                gainWin.x = Math.round(x)
                gainWin.y = Math.round(y)
                gainWin.clampPos()
            }
        }
    }

    // ---- 缩略图：手册/素材库那张图；没有就退成"名字第一个字"的小方块 ----
    // 和「怪物」那一栏同一个长相（同一件事只有一种画法）。
    component GainThumb: Item {
        id: thumb
        property string iconSource: ""
        property string monName: ""
        width: 16
        height: 16

        Image {
            id: thumbImage
            anchors.fill: parent
            source: thumb.iconSource
            visible: status === Image.Ready
            fillMode: Image.PreserveAspectFit
            smooth: false
            asynchronous: true
        }
        Rectangle {
            anchors.fill: parent
            radius: 4
            color: Theme.chip
            visible: thumbImage.status !== Image.Ready
            Text {
                anchors.centerIn: parent
                text: thumb.monName ? thumb.monName.charAt(0) : "?"
                color: Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 10
                font.bold: true
            }
        }
    }

    // 窗口投影：和主窗口同一套（灰底卡片 + 软阴影）
    WindowShadow {
        anchors.fill: gainCard
        radius: gainCard.radius
    }

    Rectangle {
        id: gainCard
        objectName: "gainCard"
        anchors.fill: parent
        anchors.margins: gainWin.inset
        radius: 10
        color: Theme.canvas
        clip: true
        focus: true
        Keys.onEscapePressed: host.closeGain()
        MouseArea { anchors.fill: parent }

        // 内容那张白卡（当前属性 + 输入 + 列表 + 合计都在它上面）
        Card {
            x: 8
            y: gainWin.headerH
            width: parent.width - 16
            height: parent.height - gainWin.headerH - 8
        }

        // ---- 抬头：拖着走 + 关 ----
        Item {
            id: gainHeader
            x: 8
            y: 0
            width: parent.width - 16
            height: gainWin.headerH

            MouseArea {
                objectName: "gainDrag"
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
                    startX = gainWin.x
                    startY = gainWin.y
                }
                onPositionChanged: function (m) {
                    if (!pressed)
                        return
                    var at = mapToGlobal(m.x, m.y)
                    gainWin.x = Math.round(startX + (at.x - pressX))
                    gainWin.y = Math.round(startY + (at.y - pressY))
                    gainWin.clampPos()
                }
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: "加属性收益"
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 14
                font.bold: true
            }

            IconBtn {
                id: gainClose
                objectName: "gainClose"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                glyph: "✕"
                glyphSize: 12
                hoverInk: Theme.danger
                hoverBack: Theme.dangerSoft
                onClicked: host.closeGain()
            }
        }

        // ---- 当前属性：一行小字（数值来自状态行）----
        Text {
            id: gainHeroText
            objectName: "gainHero"
            x: gainWin.padW
            y: gainWin.heroY
            width: gainCard.width - 2 * gainWin.padW
            height: gainWin.heroH
            verticalAlignment: Text.AlignVCenter
            text: gainWin.heroText()
            color: Theme.ink3
            font.family: Theme.uiFont
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        // ---- 三格加成 + 上界：一个数一个框，改哪个都立刻重算 ----
        Row {
            id: gainInputs
            objectName: "gainInputs"
            x: gainWin.padW
            y: gainWin.inputY
            width: gainCard.width - 2 * gainWin.padW
            height: gainWin.inputH
            spacing: 10

            Repeater {
                model: [["atk", "攻", Theme.markAtk],
                        ["def", "防", Theme.markDef],
                        ["mdef", "魔防", Theme.markMdef],
                        ["cap", "上界", Theme.accent]]
                delegate: Row {
                    spacing: 4
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData[1]
                        color: modelData[2]
                        font.family: Theme.uiFont
                        font.pixelSize: 11
                    }
                    Rectangle {
                        width: modelData[0] === "cap" ? 52 : 44
                        height: gainWin.inputH
                        radius: Theme.radius
                        color: gainField.activeFocus ? Theme.paperHi
                                                     : Theme.tile
                        border.width: 1
                        border.color: gainField.activeFocus ? Theme.accent
                                                           : Theme.hairline
                        TextField {
                            id: gainField
                            objectName: "gainField_" + modelData[0]
                            anchors.fill: parent
                            horizontalAlignment: TextInput.AlignHCenter
                            verticalAlignment: TextInput.AlignVCenter
                            background: null
                            padding: 0
                            color: Theme.ink
                            font.family: Theme.monoFont
                            font.pixelSize: 12
                            selectByMouse: true
                            // 初值来自主窗口（关掉再开，填过的数还在）
                            text: gainWin.gainValue(modelData[0])
                            // 只留数字；改一个字就重算（和伤害计算里那一行同一种手感）
                            onTextChanged: {
                                var clean = String(text).replace(/[^0-9]/g, "")
                                if (clean !== String(text)) {
                                    text = clean
                                    return
                                }
                                gainWin.setGainValue(modelData[0], clean)
                            }
                        }
                    }
                }
            }
        }

        // 一条细线把"填"和"看"分开（不画框，省视觉重量）
        Rectangle {
            x: gainWin.padW
            y: gainWin.hairY
            width: gainCard.width - 2 * gainWin.padW
            height: 1
            color: Theme.hairline
        }

        // ---- 列表：一层一组，组里每种一行（缩略图 + 名字 + 位置 + 数量 + 两个数） ----
        Flickable {
            id: gainFlick
            objectName: "gainFlick"
            x: gainWin.padW
            y: gainWin.listY
            width: gainCard.width - 2 * gainWin.padW
            height: Math.max(24, gainCard.height - gainWin.listY
                             - gainWin.footerH - 14)
            contentWidth: width
            contentHeight: gainCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: gainCol
                width: gainFlick.width
                // 层与层之间空一点：一组一个块，别糊成一片
                spacing: 6

                // 空：清单里没有剩下的怪
                Text {
                    objectName: "gainEmpty"
                    width: gainCol.width
                    height: 28
                    visible: gainWin.floors.length === 0
                    text: "清单里没有剩下的怪（清单里划掉的、或者还没读到怪）"
                    color: Theme.ink3
                    font.family: Theme.uiFont
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                    verticalAlignment: Text.AlignVCenter
                }

                Repeater {
                    model: gainWin.floors
                    delegate: Column {
                        id: gainGroup
                        objectName: "gainGroup"
                        width: gainCol.width
                        spacing: 1
                        readonly property var group: modelData || ({})

                        // 组头：层名 + 这一层还剩几种几只（小字在右边）
                        Item {
                            width: gainGroup.width
                            height: gainWin.groupH
                            Text {
                                objectName: "gainGroupName"
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                text: String(gainGroup.group.floor || "")
                                      || "没写层名"
                                color: Theme.ink2
                                font.family: Theme.uiFont
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Text {
                                objectName: "gainGroupCount"
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                text: gainWin.groupHeadText(gainGroup.group)
                                color: Theme.ink3
                                font.family: Theme.uiFont
                                font.pixelSize: 10
                            }
                        }

                        // 每种一行：缩略图 · 名字 · 位置 · ×数量 · 一只少掉 · 这种一共
                        Repeater {
                            model: gainGroup.group.species || []
                            delegate: Item {
                                id: gainRowItem
                                objectName: "gainRow"
                                width: gainGroup.width
                                height: gainWin.speciesH
                                readonly property var row: modelData || ({})
                                // 图在哪几格：点这一行就是去那儿（和路线对比同一个动作）
                                readonly property var spots:
                                    gainWin.spotsOf(gainGroup.group.floor,
                                                    row.name)
                                readonly property string iconSource:
                                    gainWin.iconOf(row.name)

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 4
                                    color: rowArea.containsMouse ? Theme.tile
                                                                 : "transparent"
                                }
                                MouseArea {
                                    id: rowArea
                                    objectName: "gainRowClick"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: gainRowItem.spots.length > 0
                                                 ? Qt.PointingHandCursor
                                                 : Qt.ArrowCursor
                                    onClicked: host.gainHighlight(
                                        gainGroup.group.floor,
                                        gainRowItem.row.name)
                                }

                                GainThumb {
                                    id: gainRowIcon
                                    x: 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    iconSource: gainRowItem.iconSource
                                    monName: String(gainRowItem.row.name || "")
                                }

                                Text {
                                    anchors.left: gainRowIcon.right
                                    anchors.leftMargin: 4
                                    width: parent.width - anchors.leftMargin
                                           - gainRowSpot.width - gainWin.colGap
                                           - gainRowCount.width - gainWin.colGap
                                           - gainRowOne.width - gainWin.colGap
                                           - gainRowAll.width - 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: String(gainRowItem.row.name || "")
                                    color: Theme.ink
                                    font.family: Theme.uiFont
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                                Text {
                                    id: gainRowSpot
                                    objectName: "gainRowSpot"
                                    width: gainWin.spotW
                                    anchors.right: gainRowCount.left
                                    anchors.rightMargin: gainWin.colGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: gainWin.spotText(gainRowItem.spots)
                                    color: Theme.ink3
                                    font.family: Theme.monoFont
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                                Text {
                                    id: gainRowCount
                                    width: gainWin.countW
                                    anchors.right: gainRowOne.left
                                    anchors.rightMargin: gainWin.colGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: "×" + Number(gainRowItem.row.count || 0)
                                    color: Theme.ink3
                                    font.family: Theme.monoFont
                                    font.pixelSize: 11
                                }
                                Text {
                                    id: gainRowOne
                                    objectName: "gainRowOne"
                                    width: gainWin.oneW
                                    anchors.right: gainRowAll.left
                                    anchors.rightMargin: gainWin.colGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: gainWin.typedGain === 0
                                          ? ""
                                          : "一只 " + Number(gainRowItem.row.one || 0)
                                    // 一点没少（加这 1 点不改变回合数）就灰下去，
                                    // 别让一排 0 抢眼睛
                                    color: Number(gainRowItem.row.one || 0) > 0
                                           ? Theme.markAtk : Theme.ink3
                                    font.family: Theme.monoFont
                                    font.pixelSize: 11
                                }
                                Text {
                                    id: gainRowAll
                                    objectName: "gainRowAll"
                                    width: gainWin.allW
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: gainWin.typedGain === 0
                                          ? ""
                                          : "共 " + Number(gainRowItem.row.all || 0)
                                    color: Number(gainRowItem.row.all || 0) > 0
                                           ? Theme.ink : Theme.ink3
                                    font.family: Theme.monoFont
                                    font.pixelSize: 11
                                    font.bold: true
                                }
                            }
                        }

                        // 手册里没数值 / 算不了的那几种：照样列出来（同样有图和位置，
                        // 那才是最该去看的那几只），右边写清为什么没算
                        Repeater {
                            model: gainGroup.group.unknown || []
                            delegate: Item {
                                objectName: "gainUnknown"
                                width: gainGroup.width
                                height: gainWin.speciesH
                                readonly property var row: modelData || ({})
                                readonly property var spots:
                                    gainWin.spotsOf(gainGroup.group.floor,
                                                    row.name)
                                readonly property string iconSource:
                                    gainWin.iconOf(row.name)

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 4
                                    color: unknownArea.containsMouse ? Theme.tile
                                                                     : "transparent"
                                }
                                // 没数值的怪最该去看一眼：点一行也去地图上圈出它
                                MouseArea {
                                    id: unknownArea
                                    objectName: "gainUnknownClick"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: spots.length > 0
                                                 ? Qt.PointingHandCursor
                                                 : Qt.ArrowCursor
                                    onClicked: host.gainHighlight(
                                        gainGroup.group.floor, row.name)
                                }

                                GainThumb {
                                    id: gainUnknownIcon
                                    x: 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    iconSource: iconSource
                                    monName: String(row.name || "")
                                }

                                Text {
                                    anchors.left: gainUnknownIcon.right
                                    anchors.leftMargin: 4
                                    width: parent.width - anchors.leftMargin
                                           - gainUnknownSpot.width - gainWin.colGap
                                           - gainUnknownCount.width - gainWin.colGap
                                           - gainUnknownWhy.width - 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: String(row.name || "")
                                    color: Theme.ink3
                                    font.family: Theme.uiFont
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                                Text {
                                    id: gainUnknownSpot
                                    objectName: "gainUnknownSpot"
                                    width: gainWin.spotW
                                    anchors.right: gainUnknownCount.left
                                    anchors.rightMargin: gainWin.colGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: gainWin.spotText(spots)
                                    color: Theme.ink3
                                    font.family: Theme.monoFont
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                                Text {
                                    id: gainUnknownCount
                                    width: gainWin.countW
                                    anchors.right: gainUnknownWhy.left
                                    anchors.rightMargin: gainWin.colGap
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: "×" + Number(row.count || 0)
                                    color: Theme.ink3
                                    font.family: Theme.monoFont
                                    font.pixelSize: 11
                                }
                                Text {
                                    id: gainUnknownWhy
                                    objectName: "gainUnknownWhy"
                                    width: gainWin.oneW + gainWin.allW
                                           + gainWin.colGap
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: String(row.reason || "") + "（没算）"
                                    color: Theme.ink3
                                    font.family: Theme.uiFont
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---- 合计（钉在底下，不跟着列表滚）----
        Item {
            id: gainFooter
            x: gainWin.padW
            width: gainCard.width - 2 * gainWin.padW
            height: gainWin.footerH
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 12

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: Theme.hairline
            }
            Text {
                objectName: "gainTotal"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                verticalAlignment: Text.AlignVCenter
                text: gainWin.totalText()
                color: (gainWin.result || {}).capped ? Theme.accent : Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 12
                font.bold: true
                elide: Text.ElideRight
            }
        }

        // ---- 四个角 / 四条边：拉大小 ----
        GainGrip {
            width: 4; height: parent.height; anchors.left: parent.left
            pullLeft: true
        }
        GainGrip {
            width: 4; height: parent.height; anchors.right: parent.right
            pullRight: true
        }
        GainGrip {
            height: 4; width: parent.width; anchors.top: parent.top
            pullTop: true
        }
        GainGrip {
            height: 4; width: parent.width; anchors.bottom: parent.bottom
            pullBottom: true
        }
        GainGrip {
            width: 8; height: 8; anchors.left: parent.left; anchors.top: parent.top
            pullLeft: true; pullTop: true
        }
        GainGrip {
            width: 8; height: 8; anchors.right: parent.right; anchors.top: parent.top
            pullRight: true; pullTop: true
        }
        GainGrip {
            width: 8; height: 8; anchors.left: parent.left
            anchors.bottom: parent.bottom
            pullLeft: true; pullBottom: true
        }
        GainGrip {
            width: 8; height: 8; anchors.right: parent.right
            anchors.bottom: parent.bottom
            pullRight: true; pullBottom: true
        }
    }
}
