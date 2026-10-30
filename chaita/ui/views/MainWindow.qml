// v12：一张卡片装下一整座塔 —— 地图 / 怪物 / 技能 / 对话。
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 主窗口本体：win.* 状态和函数、卡片框架、滚动容器，外加各子界面的挂载行。
//   界面本身都在下面这些文件夹里（一个界面一个文件夹），这份不再画它们。
// 用户拍板的就是这一版（logs/design/v12_compact.png，"就按这个设计吧"），
// 之后又加了一句："读取按钮放在地图和怪物边上，不要放在对话框"。
//
// 数据来源（全部是 controller 的塔级汇总，不再有"本层"这个主角）：
//   地图 ← mapHistory（每层一张真实截图 + 这一层有多少怪）
//   怪物 ← monsters（手册数值）× mapHistory（×N / 剩 N）
//   技能 ← skillStats（只统计地图上加过的怪）
//   对话 ← chatLog（发消息归 chat/ChatDock.qml）    读取 ← readGame()
//
// 加新界面时按"能独立存在"判断：能就单独一份文件夹，别再往这份里堆。
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
// 同目录的其它 QML（多文件加载，见 chaita/ui/loader.py）
import "."
// 一层 UI 一个文件夹（见 docs/UI_MAP.md）：
import "shared"
import "main_panel"
import "main_columns"
import "chat"
import "monster_editor"
import "icon_picker"
import "skill_picker"
import "battle_calc"
import "floor_sheet"
import "route_editor"
import "route_compare"

Window {
    id: win

    x: 0
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    // ---- 设计 tokens：颜色/字号只从这里取 ----
    // 暖纸底 + 墨字 + 一点琥珀金。三档文字明度拉开层次，不靠边框堆。
    // 配色和字体只有一处定义（Theme.qml），这里留同名别名：
    // 这份文件里 5000 行都写 `win.amber`，不为了搬家去改它们；子界面直接用 Theme。
    readonly property string uiFont: Theme.uiFont
    readonly property string monoFont: Theme.monoFont
    readonly property color paper: Theme.paper
    readonly property color paperHi: Theme.paperHi
    readonly property color paperLo: Theme.paperLo
    readonly property color edge: Theme.edge
    readonly property color hairline: Theme.hairline
    readonly property color ink: Theme.ink
    readonly property color ink2: Theme.ink2
    readonly property color ink3: Theme.ink3
    readonly property color amber: Theme.amber
    readonly property color amberInk: Theme.amberInk
    readonly property color danger: Theme.danger

    // ---- 尺寸 ----
    readonly property int padH: 12
    readonly property int padV: 12
    readonly property int navH: 22
    readonly property int navGap: 2
    readonly property int headerH: 24
    // 对话卡高度：跟着**实测**的行高走（文字会折行，不能按条数乘固定值）。
    // 行太多时给个上限（180），多出来的在卡里滚 —— 不然一句很长的回答会把窗口顶穿。
    readonly property int chatLogMax: 180
    readonly property int chatLogH: Math.min(chatLogMax, chatLog.logHeight)
    // 8（上）+ 行 + 5（行和输入条之间）+ 26（输入条）+ 7（下），最少 46
    readonly property int dockH: Math.max(46, 8 + win.chatLogH
                                              + (win.chatLogH > 0 ? 5 : 0) + 33)
    readonly property int gapA: 10
    readonly property int gapB: 12
    readonly property int bodyW: win.width - win.padH * 2
    readonly property int tileW: Math.floor((win.bodyW - 16) / 3)

    // ---- 对外契约（startup / controller 会设这些属性） ----
    property bool collapsed: false
    property string appTitle: "拆塔辅助"
    property string heroIcon: ""
    property string iconBase: ""
    property string itemBase: ""
    property bool entered: false
    // 读到新数据时顶部闪一下（折叠着也看得见）
    property string barFlash: ""
    // 刚点了哪一个「读取」（"map" / "monsters"）：按钮上只给按下它的那个显示"读取中"
    property string readingMode: ""
    // ---- 子界面 ----
    // 地图的小窗：可以多开、可以拖、可以拉大，**而且能拖到软件外面**。
    // floorWindows 是"打开着哪几层"（最后一个是最后开的），位置/大小分别记在
    // floorPositions / floorSizes 里，floorSheets 是名字 → 真窗口对象。
    // （用户："地图的小窗怎么不能移动 / 怎么不能多开 / 怎么不能放大 /
    //   地图的小窗为什么不能移动到软件之外"）
    property var floorWindows: []
    property var floorPositions: ({})
    property var floorSizes: ({})
    property var floorSheets: ({})
    // 放到别的窗口上也得跟着数据走：列表一变就把窗口补齐/收掉
    onFloorWindowsChanged: Qt.callLater(win.syncFloorSheets)
    // 折叠状态：主界面的「地图」「怪物」「技能」三栏能各自收起来（用户："地图和怪物怎么
    // 不能折叠？" → "技能也要能折叠"）。收起只留那一行标题（标题上写还剩多少），
    // 内容不占高度 —— 整窗高度是 contentHeight 绑出来的，所以窗口会跟着变矮。
    property bool mapCollapsed: false
    property bool monCollapsed: false
    property bool skillCollapsed: false
    function toggleMapSection() {
        win.mapCollapsed = !win.mapCollapsed
    }
    function toggleMonSection() {
        win.monCollapsed = !win.monCollapsed
    }
    function toggleSkillSection() {
        win.skillCollapsed = !win.skillCollapsed
    }
    // 为了兼容各处判断：最上面那层的名字（空 = 一个都没开）
    readonly property string openFloor: win.floorWindows.length > 0
                                       ? String(win.floorWindows[win.floorWindows.length - 1])
                                       : ""
    // 加怪/加资源的挑选层："" / "mon" / "item"；挑给哪一层记在 pickFloor
    property string pickMode: ""
    property string pickFloor: ""
    // 点资源图标换种类时记下"改第几条"（-1 = 新增）
    property int pickReplaceIndex: -1
    // 菜单要放进去的那个窗口（「这一层」）：Item.window 在动态创建的窗口里读出来是
    // null（实测），所以由调用方把 sheet 对象递进来
    property var pickHost: null
    // 下拉菜单挂在哪：按被点的那个「＋」按钮算位置（在小窗自己的坐标里）
    property var pickAnchor: null
    property real pickMenuX: 0
    property real pickMenuY: 0
    // 菜单列表最多多高（按小窗高度算，太矮了就会超出窗口边缘）
    property int pickListMax: 220
    // 删本层的两步确认
    property bool floorDeleteArm: false
    // 怪物编辑：monEdit 是 monsters 里的下标（-1 = 没开）
    property int monEdit: -1
    // 编辑卡片的位置（-1 = 还没拖过，按窗口居中）。用户："怎么不能移动" ——
    // 按住卡片空白处就能拖；窗口缩放时 bind 里会夹回可见范围，不会飘到窗外。
    property real monCardX: -1
    property real monCardY: -1
    property var monDraft: ({})
    property var monSkills: []
    property string monIconId: ""
    property string monIconUrl: ""
    property bool iconPicker: false
    // 素材库搜索框里的字（按名字/编号过滤；打开选图时清空）
    property string iconQuery: ""
    // 表情包式的两种状态：分组网格 / 搜索（搜索框只在搜索态出现）
    property bool iconSearchMode: false
    // 肤色库面板挂在被点的头像上方（用户："像qq的表情包显示在上方"）。
    // 这四个数在打开那一刻按头像的位置算（见 placeIconPicker），面板不靠 anchors
    // 贴边 —— 一贴边就是"半屏白板"，正是用户不要的样子。
    property real iconMenuX: 0
    property real iconMenuY: 0
    property int iconMenuW: 280
    property int iconMenuH: 330
    // 开/关都只认 iconPicker 这一个开关：预览和测试直接置位也能摆到对的位置
    onIconPickerChanged: {
        if (win.iconPicker)
            Qt.callLater(win.placeIconPicker)
    }
    // 素材库格子：所有缩略图按同一个倍数缩放（用户："所有缩略图必须以相同比例
    // 等比例放大或缩小，禁止出现图显示不全"）。格子留 4px 边，最大那张家正好装下，
    // 其余按同一倍数跟着走。用户又说"图片太大了" → 格子 36、倍数封顶 1.0（只缩不放）：
    // 一行能摆 6 张，图不超过原尺寸——放大本来就是红线。
    readonly property int iconCellSize: 36
    readonly property int iconMaxSide: controller ? controller.monsterIconMaxSide() : 32
    readonly property real iconThumbScale: Math.min(
        1, (iconCellSize - 4) / Math.max(1, iconMaxSide))
    // 整数倍用邻近取样（像素图清楚），非整数倍才开平滑，免得一边粗一边细
    readonly property bool iconThumbSmooth: iconThumbScale !== Math.floor(iconThumbScale)
    property bool skillPicker: false
    // 正在拖怪物行排序（拖动时列表不跟着滚）
    property bool monDragging: false
    // 技能下拉挂在「＋ 加技能」按钮下面（x/y 在打开时按按钮位置算）
    property real skillMenuX: 0
    property real skillMenuY: 0
    // 尺寸：展开高度默认由内容撑出来（见 refreshExpanded()），但**用户可以自己拉**。
    // 拉过就记在 userWidth / userHeight 上，之后内容怎么变都按用户拉的尺寸来，
    // 不再被"内容高度"顶回去（用户："怎么不读取就不能拉伸窗口"）。
    property int collapsedWidth: 340
    // 收起只留两行抬头（导航条 + 塔名），不再吞掉底部留白
    property int collapsedHeight: win.collapseChrome
    property int expandedWidth: 340
    property int expandedHeight: 480
    // 用户手动拉的尺寸（0 = 跟着内容走）
    property int userWidth: 0
    property int userHeight: 0
    // 最近一次"我们自己设的"高度：跟它不一样就说明用户在拖边缘
    property int autoHeight: 0
    // 折叠/展开动画期间不要把手动尺寸记错
    property bool animatingSize: false
    // 抬头这一行只有读到塔名时才占位：没塔名就整行不画
    // （用户："还没读到塔这东西删掉"、"折叠模式下的空白删掉"）。
    // 刷新 ↻ 已经挪到导航条上，所以这行不再因为"有数值"而占位。
    readonly property bool headerVisible: win.tower !== ""
    readonly property int headerBlock: win.headerVisible
                                       ? win.navGap + win.headerH : 0
    // 状态区（两行）：第一行 生命/攻击/防御/魔防，第二行 金币 + 四色钥匙
    readonly property bool statusVisible: win.statusValue("hp") !== ""
                                         || win.statusValue("atk") !== ""
                                         || win.statusValue("def") !== ""
                                         || win.statusValue("mdef") !== ""
                                         || win.statusValue("gold") !== ""
                                         || win.keyValue("yellow") !== ""
                                         || win.keyValue("blue") !== ""
                                         || win.keyValue("red") !== ""
                                         || win.keyValue("green") !== ""
    readonly property int statusH: 30
    readonly property int statusBlock: win.statusVisible ? win.statusH : 0
    // 抬头 + 状态行 + 导航条 + 上下留白 + 底部对话卡：这些是固定高度，剩下的都归内容区
    readonly property int chromeH: win.padV * 2 + win.navH + win.headerBlock
                                   + win.statusBlock + win.gapA * 2 + win.dockH
    // 折叠态只有导航条 + 抬头 + 状态行（没有内容区、没有对话卡）
    readonly property int collapseChrome: win.padV * 2 + win.navH + win.headerBlock
                                          + win.statusBlock
    // 兼容 startup 的 _apply_ui_state（它会把上次的尺寸写进来）。
    property int savedWidth: expandedWidth
    property int savedHeight: expandedHeight

    width: win.userWidth > 0 ? win.userWidth : win.expandedWidth
    // 高度不用绑定：自己算出来再赋值，才能分清"这次是内容让它变的"还是"用户拉的"。
    // 折叠那 180ms 由 Python 逐帧改尺寸（见 onCollapsedChanged）。
    height: 480
    // 太小就不好点了：给个下限，别让人把窗口拖没
    minimumWidth: 260
    // 这个下限必须比"折叠后的高度"还小：Windows 会按 minimumHeight 卡窗口高度，
    // 设成 120 的话折叠到 72/46 会被系统顶成 120，下面就留一片空白
    // （用户："折叠后还是有一大片空白"）。手动拖动时的 240 下限在 onHeightChanged 里管。
    minimumHeight: 40

    // 主窗口一关就把小窗全收掉：Qt.Tool 的独立窗口不会跟着主窗口走，
    // 留着的话进程会等它们（用户点 ✕ 后程序退不掉）
    onClosing: win.closeAllSheets()

    onWidthChanged: {
        // 手动拉的宽度记下来（自动布局给的宽度不记）
        if (!win.collapsed && win.width !== win.expandedWidth
                && Math.abs(win.width - win.userWidth) > 1)
            win.userWidth = Math.round(win.width)
        win.rememberGeometry()
        // 选图面板是按打开那一刻的头像算的位置：窗口一变就收起来（用户拍板）
        win.closeIconPickerIfOpen()
    }
    onHeightChanged: {
        if (!win.collapsed && !win.animatingSize) {
            if (win.height < 240) {
                // 太矮（抬头 + 对话卡都放不下）就顶回 240，并把这当成用户的新尺寸
                win.userHeight = 240
                win.autoHeight = 240
                win.height = 240
            } else if (Math.abs(win.height - win.autoHeight) > 1) {
                // 不是我们自己设的高度 → 用户在拖边缘，按他的来
                win.userHeight = Math.round(win.height)
                win.autoHeight = win.height
            }
        }
        win.rememberGeometry()
        win.closeIconPickerIfOpen()
    }
    onXChanged: win.rememberGeometry()
    onYChanged: win.rememberGeometry()

    function rememberGeometry() {
        if (typeof controller === "undefined" || !controller)
            return
        controller.rememberWindow(Math.round(win.x), Math.round(win.y),
                                  win.collapsed ? 0 : Math.round(win.width),
                                  win.collapsed ? 0 : Math.round(win.height))
    }

    // ---- 塔级汇总 ----
    // 每只怪在整座塔里各有多少只（按地图记录累加：同名怪在不同层算在一起）
    function monTotals() {
        var out = {}
        var list = win.floorEntries()
        for (var i = 0; i < list.length; i++) {
            var mons = (list[i] || {}).mons || []
            for (var j = 0; j < mons.length; j++) {
                var m = mons[j] || {}
                var name = String(m.name || "").trim()
                if (name === "")
                    continue
                var n = parseInt(m.count, 10)
                if (isNaN(n) || n < 0)
                    n = 0
                var row = out[name]
                if (!row) {
                    row = { total: 0, left: 0 }
                    out[name] = row
                }
                row.total += n
                if (!m.done)
                    row.left += n
            }
        }
        return out
    }

    function floorEntries() {
        return (controller ? controller.mapHistory : null) || []
    }

    // 一条怪物行要显示的所有东西（模板里不写业务判断）
    function monsterRows() {
        var totals = win.monTotals()
        var db = (controller ? controller.monsters : null) || []
        var rows = []
        var seen = {}
        for (var i = 0; i < db.length; i++) {
            var m = db[i] || {}
            var name = String(m.name || "").trim()
            if (name === "" || seen[name])
                continue
            seen[name] = true
            var t = totals[name] || { total: 0, left: 0 }
            // 手册里读到的怪**都列出来**（用户："怪物读不进去"——
            // 以前只要地图上还没记，读完手册这一栏是空的）。地图上的才有 ×N/剩 N。
            rows.push({ name: name, icon: m.icon || "", total: t.total,
                        left: t.left, dbIndex: i, onMap: t.total > 0,
                        skill: win.skillText(m), stats: win.statLine(m) })
        }
        // 顺序就是"用户自己排的顺序"（_monsters 的顺序）：按住一行能上下拖。
        // 地图上加过、手册里还没读到的怪没有可拖的行，按名字挂在最后。
        var extras = []
        for (var other in totals) {
            if (seen[other])
                continue
            extras.push({ name: other, icon: "", total: totals[other].total,
                          left: totals[other].left, dbIndex: -1, onMap: true,
                          skill: "", stats: "" })
        }
        extras.sort(function (a, b) {
            return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0)
        })
        return rows.concat(extras)
    }

    // 能拖（= 在手册列表里）的行数：Python 算落点时按行高数行，多出来的
    // "地图上才有"的怪不算进去
    function dbRowCount() {
        var n = 0
        for (var i = 0; i < win.monRows.length; i++) {
            if ((win.monRows[i] || {}).dbIndex >= 0)
                n++
        }
        return n
    }

    // ---- 拖动怪物行：调整顺序 ----
    // 顺序是用户自己的（常看的怪放前面）。落点由 Python 每 40ms 读系统光标算
    // （和窗口拖动、怪物排序同一套）：指针一离开那一行，QML 的 MouseArea 会收到
    // canceled，靠抓取拖拽会断在半路（实测）。这里只负责"从哪一行开始"和"收尾"。
    function beginMonDrag(from, rowHeight) {
        if (from < 0 || from >= win.dbRowCount() || !controller)
            return
        // 行高由 delegate 传进来；第一行在窗口里的位置问三栏要（别跨文件摸 monRep）
        var top = body.firstRowTop()
        if (top < 0)
            return
        win.monDragging = true
        controller.monDragStart(from, win.y + top, rowHeight, win.dbRowCount())
    }

    function endMonDrag() {
        win.monDragging = false
        controller.monDragFinish()
    }

    function skillText(m) {
        var items = (m && m.skill_items) || []
        var names = []
        for (var i = 0; i < items.length; i++) {
            var token = String((items[i] || {}).name || "").trim()
            if (token !== "" && names.indexOf(token) < 0)
                names.push(token)
        }
        if (names.length > 0)
            return names.join(" · ")
        var raw = String((m && m.skills) || "").trim()
        if (raw === "")
            return ""
        return raw.split(/[\s,，、\/;；]+/).filter(function (x) { return x !== "" }).join(" · ")
    }

    function statLine(m) {
        var parts = []
        if (m && m.hp) parts.push("生命 " + m.hp)
        if (m && m.atk) parts.push("攻 " + m.atk)
        if (m && m.def) parts.push("防 " + m.def)
        return parts.join(" · ")
    }

    // 一行一个技能：多少只带它、还剩几只（都按整座塔算）
    function skillRows() {
        var stats = (controller ? controller.skillStats : null) || []
        var totals = win.monTotals()
        var rows = []
        for (var i = 0; i < stats.length; i++) {
            var s = stats[i] || {}
            var mons = s.mons || []
            var total = 0
            var left = 0
            var members = []
            var seen = {}
            for (var j = 0; j < mons.length; j++) {
                var name = String((mons[j] || {}).name || "").trim()
                if (name === "" || seen[name])
                    continue
                seen[name] = true
                var t = totals[name]
                if (!t)
                    continue
                members.push(name)
                total += t.total
                left += t.left
            }
            rows.push({ name: String(s.skill || ""), total: total, left: left,
                        members: members })
        }
        rows.sort(function (a, b) {
            if (a.total !== b.total)
                return b.total - a.total
            return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0)
        })
        return rows
    }

    // 汇总只统计"地图上有记录"的怪；只有手册记录时给"手册 N 种"
    function monSummary(rows) {
        if (!rows || rows.length === 0)
            return ""
        var total = 0
        var left = 0
        var mapped = 0
        for (var i = 0; i < rows.length; i++) {
            if (!rows[i].onMap)
                continue
            mapped += 1
            total += rows[i].total
            left += rows[i].left
        }
        if (mapped === 0)
            return "手册 " + rows.length + " 种 · 地图还没记"
        return mapped + " 种 · 共 " + total + " 只 · 剩 " + left
    }

    function skillSummary(rows) {
        if (!rows || rows.length === 0)
            return ""
        // "涉及多少只"按怪去重：一只怪带两个技能不能算两倍
        var totals = win.monTotals()
        var seen = {}
        var count = 0
        for (var i = 0; i < rows.length; i++) {
            var members = rows[i].members || []
            for (var j = 0; j < members.length; j++) {
                if (seen[members[j]])
                    continue
                seen[members[j]] = true
                var t = totals[members[j]]
                if (t)
                    count += t.total
            }
        }
        return rows.length + " 种 · 涉及 " + count + " 只"
    }

    // 有没有图：Image 的 source 是 url 类型，跟 "" 做 !== 比较不可靠（实测占位块不出来），
    // 所以统一在 JS 里判断，模板只绑这个布尔值。
    function hasUrl(url) {
        return !!(url && String(url) !== "")
    }

    function floorMeta(entry) {
        var mons = (entry || {}).mons || []
        var kinds = 0
        var count = 0
        for (var i = 0; i < mons.length; i++) {
            var m = mons[i] || {}
            if (String(m.name || "").trim() === "")
                continue
            kinds += 1
            var n = parseInt(m.count, 10)
            if (!isNaN(n) && n > 0)
                count += n
        }
        if (kinds === 0)
            return "还没记怪"
        return kinds + " 怪 · " + count + " 只"
    }

    // 底部对话：**完整历史**（用户："我需要完整的历史，这才符合直觉"）。
    // 内容长就折行（不再按一行截断，用户："每一行的内容超出行的部分会被截断"）；
    // 卡片最多长到 180，更多的在卡里滚、并且自动滚到最新一句。
    // AI 正在想的时候，最后多一行"正在想…"。
    // 没有对话就什么都不显示（用户："默认提示都删掉，真low"）。
    function chatLines() {
        var log = (controller ? controller.chatLog : null) || []
        var lines = []
        for (var i = 0; i < log.length; i++)
            lines.push(log[i] || ({}))
        if (controller && controller.chatting)
            lines.push({ who: "AI", text: "正在想…", at: "" })
        return lines
    }


    function statusValue(key) {
        var state = (controller ? controller.statusData : null) || {}
        var value = state[key]
        if (value === undefined || value === null)
            return ""
        return String(value)
    }

    // 四色钥匙：statusData.keys 里是数字或空
    function keyValue(name) {
        var state = (controller ? controller.statusData : null) || {}
        var keys = state.keys || ({})
        var value = keys[name]
        if (value === undefined || value === null)
            return ""
        return String(value)
    }

    function towerName() {
        // 没读到塔就空着，不写"还没读到塔"这种占位文案（用户："这东西删掉"）
        return String((controller ? controller.towerLabel : "") || "")
    }

    // 读到一半 / 出错时给一句话（没出错就不占高度）
    function noticeText() {
        var err = String((controller ? controller.errorText : "") || "")
        if (err !== "")
            return err
        return ""
    }

    function readHint() {
        if (!controller)
            return ""
        // 正在读的时候按钮自己会写「读取中」，这行就别重复一遍
        if (controller.reading)
            return ""
        // statusText 是整段状态（属性/道具/金币），这里只要"几点读的"那一刻
        var at = String(controller.statusAt || "")
        return at !== "" ? at + " 读取" : ""
    }

    // ---- 内容驱动的窗口高度 ----
    // 高度是**绑定**出来的（expandedHeight = 固定高度 + 内容高度），内容一变窗口
    // 就跟着变，不去猜"什么时候布局好了"。折叠/展开那 180ms 由 Python 逐帧改尺寸
    // （QML 自己驱动不了 Window 的几何，实测），动画结束后再 bindBackSize()。
    function middleCap() {
        var avail = win.screen ? win.screen.desktopAvailableHeight : 900
        var cap = Math.round(avail * 0.72) - win.chromeH
        return Math.max(180, Math.min(560, cap))
    }

    function contentHeight() {
        var inner = flick ? flick.contentHeight : 0
        return Math.ceil(win.chromeH + Math.min(inner, win.middleCap()))
    }

    // 内容行数变了的时候调这个（flick.contentHeight 变了会自己叫）
    function refreshExpanded() {
        var target = win.contentHeight()
        if (target !== win.expandedHeight)
            win.expandedHeight = target
    }

    // 按"用户拉过的尺寸 > 内容高度"算一次窗口高度，然后赋值。
    // height 不走绑定：只有自己赋过的值记进 autoHeight，别的变化才算用户拖的。
    function applyAutoSize() {
        win.refreshExpanded()
        if (win.collapsed)
            return
        var target = win.userHeight > 0 ? win.userHeight : win.expandedHeight
        target = Math.max(240, Math.round(target))
        if (Math.abs(win.height - target) > 1) {
            win.autoHeight = target
            win.height = target
        } else {
            win.autoHeight = win.height
        }
    }

    // 折叠动画收工后把尺寸按"用户尺寸 > 内容高度"重新算一次
    // （上次退出时的尺寸由 startup 直接写进 userWidth / userHeight）
    function bindBackSize() {
        win.applyAutoSize()
    }

    // 回到"跟着内容走"（想恢复自动高度时调；现在界面上没有入口，留给测试/以后用）
    function forgetManualSize() {
        win.userWidth = 0
        win.userHeight = 0
        win.applyAutoSize()
    }

    function sync() {
        win.monRows = win.monsterRows()
        win.skills = win.skillRows()
        win.chats = win.chatLines()
        win.monAgg = win.monSummary(win.monRows)
        win.skillAgg = win.skillSummary(win.skills)
        win.floorList = win.floorEntries()
        win.tower = win.towerName()
        win.notice = win.noticeText()
        win.readTip = win.readHint()
        win.sessionHint = String((controller ? controller.sessionHint : "") || "")
        flick.contentY = 0
        win.refreshTasks()
        // 行变了之后布局要过一轮才算得对高度：等这一轮完了再定窗口高度
        Qt.callLater(win.applyAutoSize)
    }

    // ---- 路线链（docs/ROUTE.md）----
    // 一条路线 = 地图上长按玩家拖出来的格子（按走过的顺序、允许回头）。每格能填
    // "这一格有什么"（怪 / 资源 / 门）；「计算」沿链跑一遍，掉血写格后、总掉血在右端。
    // 公式用的是 `chaita/game/battle.py` 那一套（和伤害计算同一个，不另写一份）。
    // 路线窗口多开：一条路线一扇窗（和「这一层」小窗同款）。key = 层#序号。
    property var routeSheets: ({})
    property var routeOrder: []

    // 每扇窗自己的上下文（ctx）：floor/index/cells/结果/英雄/菜单/编辑卡片。
    // 这些以前是单份的 route* 属性，多开之后必须每窗一份。
    function newRouteCtx(floor, index) {
        return { "floor": String(floor || ""), "index": Number(index),
                 "cells": [], "chainRows": [], "result": ({}),
                 "hero": win.heroNow(),
                 "menu": "", "menuCell": -1, "pickTab": "monster",
                 "pickData": [], "menuX": 0, "menuY": 0,
                 "editLayer": false, "editCell": -1, "editData": ({}),
                 "editParams": [] }
    }
    function routeKey(ctx) {
        return String(ctx.floor || "") + "#" + String(ctx.index)
    }
    // ctx 是普通 JS 对象，改它的字段不会触发 QML 通知；每次改完把整份重新塞回
    // 窗口的 ctx 属性（新对象）才会重画。
    function routeNotify(ctx) {
        var sheet = win.routeSheets[win.routeKey(ctx)]
        if (sheet)
            sheet.ctx = Object.assign({}, ctx)
    }

    // ---- 兼容「当前路线」的只读视图（tests/helpers 读这几个；取最后开的那扇）----
    readonly property var routeWindow: {
        if (win.routeOrder.length === 0)
            return null
        return win.routeSheets[win.routeOrder[win.routeOrder.length - 1]] || null
    }
    readonly property var routeCtx: {
        var sheet = win.routeWindow
        return (sheet && sheet.ctx) || ({})
    }
    readonly property string routeFloor: String(win.routeCtx.floor || "")
    readonly property int routeIndex: Number(win.routeCtx.index === undefined
                                             ? -1 : win.routeCtx.index)
    readonly property var routeResult: win.routeCtx.result || ({})
    readonly property var routeCells: win.routeCtx.cells || []
    readonly property string routePickTab: String(win.routeCtx.pickTab || "monster")
    readonly property bool routeEditLayer: !!win.routeCtx.editLayer

    // 魔塔一层就是 13×13（用户拍板，不读 AI —— 模型数出 14/15 反而把格子带偏）
    readonly property int routeCols: 13

    // ---- 格子编辑模式（用户："小窗打开编辑模式……地图上覆盖坐标系……
    // 长按拖到下方词条上把坐标记录给词条……编辑结束修改 json"）----
    property bool gridEditOn: false
    property string gridEditFloor: ""
    // 鼠标悬停的那一格（没有 = {}）；正在拖的那一格（没有 = {}）
    property var gridHover: ({})
    property var gridDrag: ({})
    // Ctrl+点勾选的格子（多选）：一次性把它们记给同一个词条
    property var gridMulti: []
    // 当前选中的怪/资源名（空 = 没选）：图上只有它的格子是黄的
    property string gridSelected: ""

    // Ctrl+点一格：勾上 / 取消（同一个格子再点一次就取消）
    function gridMultiToggle(row, col) {
        var list = []
        var found = false
        for (var i = 0; i < win.gridMulti.length; i++) {
            var c = win.gridMulti[i] || ({})
            if (Number(c.row) === Number(row) && Number(c.col) === Number(col)) {
                found = true
                continue
            }
            list.push({ "row": Number(c.row), "col": Number(c.col) })
        }
        if (!found)
            list.push({ "row": Number(row), "col": Number(col) })
        win.gridMulti = list
    }

    function gridEditToggle(floorText) {
        if (win.gridEditOn && win.gridEditFloor === String(floorText)) {
            win.gridEditOn = false
            win.gridEditFloor = ""
        } else {
            win.gridEditOn = true
            win.gridEditFloor = String(floorText || "")
        }
        win.gridHover = ({})
        win.gridDrag = ({})
        win.gridSelected = ""
        win.gridMulti = []
    }

    // 选中/取消选中一个词条（再点同一个 = 取消）
    function gridSelect(name) {
        var want = String(name || "")
        win.gridSelected = (want !== "" && win.gridSelected === want) ? "" : want
    }

    // 这一层 grid 里 (row,col) 记的是什么（名字；空 = 没记）
    function gridCellName(floorText, row, col) {
        var cells = controller ? controller.gridCells(String(floorText || "")) : []
        for (var i = 0; i < cells.length; i++) {
            var cell = cells[i] || ({})
            if (Number(cell.row) === Number(row) && Number(cell.col) === Number(col))
                return String(cell.name || "")
        }
        return ""
    }

    // 这个怪/资源名出现在哪些格（编辑模式给词条标位置）
    function gridPositionsFor(floorText, name, effect) {
        var positions = controller
                ? controller.gridPositions(String(floorText || ""),
                                           String(name || ""),
                                           String(effect || ""))
                : []
        var out = []
        for (var i = 0; i < positions.length; i++)
            out.push({ "row": Number(positions[i].row),
                       "col": Number(positions[i].col) })
        return out
    }

    // 拖到词条上：把 (row,col) 记成 kind/name；拖到地图空处 = 清掉
    function gridAssign(row, col, kind, name, effect) {
        if (!controller || !win.gridEditOn)
            return
        controller.assignGridCell(win.gridEditFloor, Number(row), Number(col),
                                  String(kind || ""), String(name || ""),
                                  String(effect || ""))
        win.gridDrag = ({})
        win.gridHover = ({})
    }

    // 一次落多格（Ctrl 多选后拖到词条上）：坐标整批交给 controller，只改一遍数据。
    // 名字/效果必须由调用方在**进来之前**取好：每格一改就会重建那一行词条，
    // 循环里再读词条拿到的是空的（用户："编辑模式多选添加有问题"）。
    function gridAssignMany(cells, kind, name, effect) {
        if (!controller || !win.gridEditOn)
            return
        var list = []
        for (var i = 0; i < (cells || []).length; i++) {
            var cell = cells[i] || ({})
            list.push({ "row": Number(cell.row), "col": Number(cell.col) })
        }
        if (list.length === 0)
            return
        controller.assignGridCells(win.gridEditFloor, list,
                                   String(kind || ""), String(name || ""),
                                   String(effect || ""))
        win.gridDrag = ({})
        win.gridHover = ({})
        win.gridMulti = []          // 落完就清掉勾选，别留到下一次
    }

    // 一格在图上的边长（显示坐标）：图实际画出来多宽 ÷ 13
    function routeCell(floorText, drawnWidth) {
        return Math.max(4, Number(drawnWidth) / win.routeCols)
    }

    // 松手生成一条路线：存进那一层，并且马上把这条链摆出来（交互路线）
    function storeRoute(floorText, cells) {
        if (!controller)
            return
        var floor = String(floorText || "")
        var index = controller.saveRoute(floor, cells || [])
        if (index < 0)
            return
        // 备注不再往里写"计算值"：计算那部分由界面实时算、只读显示；
        // 备注只留用户手写的话（用户："备注改成两部分，计算和手写"）。
        win.openRoute(floor, index)
    }

    // 一条路线**当前**的计算值（走完之后的血/攻/防/魔防，只读显示）
    function routeStatsFor(floorText, routeIndex) {
        if (!controller)
            return ""
        var cells = controller.routeCells(String(floorText || ""),
                                          Number(routeIndex))
        return win.routeStatsMemo(cells)
    }

    // 这一层有几条路线 → `[{index, at, memo, cells}]`（清单里的「路线」行读它）
    function floorRoutes(floorText) {
        var entry = win.floorEntry(floorText)
        var rows = entry ? (entry.routes || []) : []
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i] || ({})
            out.push({ "index": i, "at": String(row.at || ""),
                       "memo": String(row.memo || ""),
                       "cells": row.cells || [] })
        }
        return out
    }

    // 打开一层里的某条路线：一条一扇窗；点已开的那条 = 提到最前。
    function openRoute(floorText, routeIndex) {
        if (!controller)
            return
        var ctx = win.newRouteCtx(floorText, routeIndex)
        var key = win.routeKey(ctx)
        var sheet = win.routeSheets[key]
        if (sheet) {
            win.routeSync(sheet.ctx)   // 内容可能被改了，重取一遍
            sheet.raise()
            sheet.requestActivate()
            return
        }
        sheet = routeWindowComp.createObject(null, { "ctx": ctx })
        if (!sheet)
            return
        win.routeSheets[key] = sheet
        win.routeOrder = win.routeOrder.concat([key])
        sheet.place()
        // 多开时级联：每多开一扇，往下往右错开一点，别全叠在同一个落点
        var opened = win.routeOrder.length - 1
        if (opened > 0) {
            sheet.x = Math.round(sheet.x + opened * 26)
            sheet.y = Math.round(sheet.y + opened * 26)
            sheet.clampPos()
        }
        sheet.show()
        win.routeSync(ctx)
        // 点路线要把它**提到最前面**（用户："我点路线为什么窗口不自动回到最前面"）
        try {
            sheet.raise()
            sheet.requestActivate()
        } catch (error) {}
    }

    function closeRoute(ctx) {
        if (!ctx)
            return
        ctx.menu = ""
        ctx.menuCell = -1
        var key = win.routeKey(ctx)
        var sheet = win.routeSheets[key]
        if (!sheet)
            return
        delete win.routeSheets[key]
        win.routeOrder = win.routeOrder.filter(function (k) { return k !== key })
        sheet.destroy()
    }

    // 人物状态：打开链、点「计算」时都重新取一次（状态行刚读到的就是最新）
    function heroNow() {
        var out = { "hp": 0, "atk": 0, "def": 0, "mdef": 0 }
        var hero = controller ? controller.battleHero() : null
        if (hero) {
            for (var key in out)
                out[key] = Number(hero[key] || 0)
        }
        return out
    }

    // 从记录里把这条链的格子拿一份到 QML 上（每次改完都要再取一次）
    function routeSync(ctx) {
        var entry = win.floorEntry(ctx.floor)
        var routes = entry ? (entry.routes || []) : []
        var route = routes[ctx.index] || null
        // 内容按坐标从这一层**当前**的 grid 实时取：编辑模式改了 grid，
        // 路线链跟着变（用户："路线图里的资源数值和地图下我调过的数值不一致"）
        ctx.cells = controller
                ? controller.routeCells(ctx.floor, ctx.index)
                : (route ? (route.cells || []).slice(0) : [])
        var shown = []
        // 走过的格子只摆**第一次**：怪打死 / 资源捡走以后，回头再走这格就是空的
        // （用户："走过怪物后怪物就死了"）
        var seen = {}
        for (var i = 0; i < ctx.cells.length; i++) {
            var cell = ctx.cells[i] || ({})
            if (!win.routeShown(cell))
                continue
            var key = win.routeCellKey(cell)
            if (seen[key])
                continue
            seen[key] = true
            shown.push({ "index": i, "cell": cell })
        }
        ctx.chainRows = shown
        win.routeNotify(ctx)
    }

    // 一格的唯一 key（行列）：判断"这一格是不是又走了一遍"
    function routeCellKey(cell) {
        return Number((cell || {}).row) + "," + Number((cell || {}).col)
    }

    // 一格在哪儿：层名 + 行列。路线对比表前面那一列只认坐标和缩略图
    // （用户："不要写怪物名字！！！用缩略图和坐标！！"），点一行还要按它
    // 在地图上圈出这一格，所以坐标得跟着步骤一起传。
    function routeCellSpot(cell) {
        return { "floor": String((cell || {}).floor || ""),
                 "row": Number((cell || {}).row),
                 "col": Number((cell || {}).col) }
    }

    // 链上只摆怪/宝石/血瓶：空的走过格、门都不显示（用户："非怪和宝石血瓶不需要显示"）
    function routeShown(cell) {
        var kind = String((cell || {}).kind || "")
        return kind === "monster" || kind === "item"
    }

    // 格子上那一行小字：格 2,3（行列从 1 数，和"第几行第几列"一致）
    function routeLabel(cell) {
        return "格 " + (Number((cell || {}).row) + 1) + ","
                     + (Number((cell || {}).col) + 1)
    }

    function routeCellIcon(cell) {
        var kind = String((cell || {}).kind || "")
        if (kind !== "monster" && kind !== "item")
            return ""
        return win.routeRowIcon(kind, (cell || {}).icon)
    }

    // 怪用手册里裁下来的图，资源用 assets/items 里的图（和伤害计算同一个规矩）
    function routeRowIcon(kind, icon) {
        if (String(kind) === "item")
            return win.itemIcon(String(icon || ""))
        return String(icon || "")
    }

    // 缩略图没有图标时，写名字的头一个字（怪/资源的图标来自手册/素材库，
    // 读不到的时候至少认得出是哪一类）
    function routeCellGlyph(cell) {
        var name = String((cell || {}).name || "")
        return name !== "" ? name.substring(0, 1) : ""
    }

    function routeComputed(ctx) {
        return (ctx.result || ({})).total_damage !== undefined
    }

    function routeStepResult(ctx, cellIndex) {
        var rows = (ctx.result || ({})).rows || []
        return rows[cellIndex] || ({})
    }

    // 掉血写在格子后面（和伤害计算同一个写法："（−930）"）；
    // 没算过是"—"，算不出来是"打不了"；手册里没有这只怪（名字对不上）是"没数值"
    function routeCellDamage(ctx, cellIndex) {
        var cell = ctx.cells[cellIndex] || ({})
        if (String(cell.kind || "") !== "monster")
            return ""
        if (!Number(cell.hp))
            return "（没数值）"
        if (!win.routeComputed(ctx))
            return "—"
        var row = win.routeStepResult(ctx, cellIndex)
        if (row.ok === false)
            return "（打不了）"
        if (row.lethal)
            return "（−" + win.fmt(row.damage) + "）打不过"
        if (row.ok)
            return "（−" + win.fmt(row.damage) + "）"
        return "—"
    }

    // 一格 → 「伤害计算」里的一步：怪/资源原样送，门/空格按 empty 占位
    //（占位不能省：界面上的格子和结果是按下标对齐的）
    // 走过一次就"清空"：怪打死了、资源捡走了，回头再走这格不再算一遍
    //（用户："走过怪物后怪物就死了"）
    function routeSteps(ctx) {
        return win.routeStepsFor(ctx.cells)
    }

    function routeStepsFor(cells) {
        var steps = []
        var seen = {}
        for (var i = 0; i < (cells || []).length; i++) {
            var cell = cells[i] || ({})
            var kind = String(cell.kind || "")
            if (kind !== "monster" && kind !== "item") {
                steps.push({ "kind": "empty" })
                continue
            }
            var key = win.routeCellKey(cell)
            if (seen[key]) {
                steps.push({ "kind": "empty" })
                continue
            }
            seen[key] = true
            var spot = win.routeCellSpot(cell)
            if (kind === "monster")
                // 坐标只给怪带：路线对比表一行一只怪，靠它画坐标、点一行去地图上圈格
                //（资源不进对比表，不带这些字段，复制出去的 JSON 也就不变胖）
                steps.push({ "kind": "monster",
                             "name": String(cell.name || ""),
                             "hp": Number(cell.hp) || 0,
                             "atk": Number(cell.atk) || 0,
                             "def": Number(cell.def) || 0,
                             "icon": String(cell.icon || ""),
                             "count": Math.max(1, Number(cell.count) || 1),
                             "skills": cell.skills || [],
                             "floor": spot.floor,
                             "row": spot.row,
                             "col": spot.col })
            else
                steps.push({ "kind": "item",
                             "name": String(cell.name || ""),
                             "effect": String(cell.effect || ""),
                             "icon": String(cell.icon || ""),
                             "count": Math.max(1, Number(cell.count) || 1) })
        }
        return steps
    }

    // 一条路线的默认备注：走完这条路之后的血/攻/防/魔防
    //（用户："备注默认是玩家路线最后的血量攻击防御魔防"）
    function routeStatsMemo(cells) {
        if (!controller)
            return ""
        var result = controller.computeBattle(JSON.stringify({
            "hero": win.heroNow(),
            "steps": win.routeStepsFor(cells || []) })) || ({})
        var stats = result.stats || ({})
        if (stats.hp === undefined)
            return ""
        return "血 " + win.fmt(stats.hp) + " · 攻 " + win.fmt(stats.atk)
             + " · 防 " + win.fmt(stats.def) + " · 魔防 " + win.fmt(stats.mdef)
    }

    function routeCompute(ctx) {
        if (!controller || !ctx)
            return
        ctx.hero = win.heroNow()
        var payload = JSON.stringify({ "hero": ctx.hero,
                                       "steps": win.routeSteps(ctx) })
        ctx.result = controller.computeBattle(payload) || ({})
        win.routeNotify(ctx)
    }

    // 这条路线转成和「复制」一模一样的那份 JSON（拖拽和粘贴共用一种格式）
    function routeStepsJson(ctx) {
        if (!ctx)
            return ""
        // 同层路线的格子没记层名（只有跨层的才每格带 floor）：补成这条路线自己的层，
        // 不然对比表拿到坐标也不知道该开哪一层的地图
        var floor = String((ctx || {}).floor || "")
        var steps = win.routeSteps(ctx)
        var out = []
        for (var i = 0; i < steps.length; i++) {
            var step = steps[i] || ({})
            if (String(step.kind || "") === "empty")
                continue
            if (String(step.floor || "") === "")
                step.floor = floor
            out.push(step)
        }
        if (out.length === 0)
            return ""
        return JSON.stringify({ "steps": out })
    }

    // 「复制」：把这条链上的怪/宝石/血瓶转成伤害计算的步骤，空走过格不要；
    // 直接写进系统剪贴板（真复制），伤害计算/路线对比「粘贴」或 Ctrl+V 能读回来。
    function routeCopy(ctx) {
        if (!controller || !ctx)
            return
        var text = win.routeStepsJson(ctx)
        if (text === "")
            return
        controller.clipboardCopy(text)
    }

    // 从系统剪贴板解析路线步骤：只认「复制路线」写进去的那种 JSON，
    // 解析失败 / 形状不对 / 混进不认识的东西 → 整段都不收（返回空）。
    function routeParseClipboard(text) {
        var data = null
        try {
            data = JSON.parse(String(text || ""))
        } catch (e) {
            return []
        }
        var rows = data ? data.steps : null
        if (!(rows instanceof Array))
            return []
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i] || ({})
            var kind = String(row.kind || "")
            if (kind === "monster")
                out.push({ "kind": "monster",
                           "name": String(row.name || ""),
                           "hp": Number(row.hp) || 0,
                           "atk": Number(row.atk) || 0,
                           "def": Number(row.def) || 0,
                           "icon": String(row.icon || ""),
                           "count": Math.max(1, Number(row.count) || 1),
                           "skills": row.skills || [],
                           // 坐标：对比表画「缩略图 + 坐标」、点一行去地图上圈格用
                           "floor": String(row.floor || ""),
                           "row": Number(row.row),
                           "col": Number(row.col) })
            else if (kind === "item")
                out.push({ "kind": "item",
                           "name": String(row.name || ""),
                           "effect": String(row.effect || ""),
                           "icon": String(row.icon || ""),
                           "count": Math.max(1, Number(row.count) || 1) })
            else
                return []
        }
        return out
    }

    function routeTotal(ctx) {
        if (!win.routeComputed(ctx))
            return ""
        return "总掉血 " + win.fmt(ctx.result.total_damage)
    }

    function routeLeft(ctx) {
        if (!win.routeComputed(ctx))
            return ""
        return "剩血 " + win.fmt(ctx.result.hp_after)
    }

    // 沿链走完人倒了（剩血 0）：总掉血那行标红，别让人以为还能继续打
    function routeDead(ctx) {
        return win.routeComputed(ctx) && Number(ctx.result.hp_after) <= 0
    }

    // 点格子：填这一格有什么（怪 / 资源 / 门 / 清空）
    function openRouteMenu(ctx, cellIndex) {
        if (!ctx)
            return
        ctx.menuCell = Number(cellIndex)
        ctx.menu = "cell"
        ctx.pickTab = "monster"
        win.routeRefreshPick(ctx)
        win.routeNotify(ctx)
    }

    function closeRouteMenu(ctx) {
        ctx.menu = ""
        ctx.menuCell = -1
        win.routeNotify(ctx)
    }

    function routeSwitchTab(ctx, tab) {
        if (ctx.pickTab === tab)
            return
        ctx.pickTab = tab
        win.routeRefreshPick(ctx)
        win.routeNotify(ctx)
    }

    function routeRefreshPick(ctx) {
        ctx.pickData = win.routePickRows(ctx)
        win.routeMenuPlace(ctx)
        Qt.callLater(function () { win.routeMenuPlace(ctx) })
        win.routeNotify(ctx)
    }

    function routePickRows(ctx) {
        var out = []
        if (ctx.pickTab === "item") {
            // 资源只列宝石和血瓶（用户："非怪和宝石血瓶不需要显示"）
            var items = controller ? controller.routeItems() : []
            for (var i = 0; i < items.length; i++)
                out.push({ "kind": "item", "entry": items[i] })
            return out
        }
        var mons = controller ? controller.battleMonsters() : []
        for (var j = 0; j < mons.length; j++)
            out.push({ "kind": "monster", "entry": mons[j] })
        return out
    }

    function routeMenuPlace(ctx) {
        var sheet = win.routeSheets[win.routeKey(ctx)]
        if (sheet && sheet.placeMenu)
            sheet.placeMenu()
    }

    // ---- 点缩略图改参数（和伤害计算点缩略图出来的是同一个"改参数"卡片）----
    function routeCopyCell(cell) {
        var copy = {}
        for (var name in (cell || {}))
            copy[name] = cell[name]
        var skills = []
        var list = (cell || {}).skills || []
        for (var i = 0; i < list.length; i++) {
            var item = list[i] || ({})
            var s = {}
            for (var key in item)
                s[key] = item[key]
            var params = {}
            for (var field in (item.params || {}))
                params[field] = item.params[field]
            s.params = params
            skills.push(s)
        }
        copy.skills = skills
        return copy
    }

    // 技能参数行：路线格里存的技能是精简过的（没 schema），从手册那只怪身上补
    function routeEditParamsFor(cell) {
        var out = []
        var skills = (cell || {}).skills || []
        var monsterSkills = []
        if (String((cell || {}).kind || "") === "monster" && controller) {
            var mons = controller.battleMonsters()
            for (var i = 0; i < mons.length; i++) {
                if (String(mons[i].name || "") === String((cell || {}).name || "")) {
                    monsterSkills = mons[i].skills || []
                    break
                }
            }
        }
        for (var j = 0; j < skills.length; j++) {
            var skill = skills[j] || ({})
            var schema = []
            for (var m = 0; m < monsterSkills.length; m++) {
                var ms = monsterSkills[m] || ({})
                if (String(ms.name || "") === String(skill.name || "")) {
                    schema = ms.schema || []
                    break
                }
            }
            for (var k = 0; k < schema.length; k++) {
                var item = schema[k] || ({})
                out.push({ "skillIndex": j,
                           "skillName": String(skill.name || ""),
                           "field": String(item.field || ""),
                           "label": String(item.label || item.field || ""),
                           "unit": String(item.unit || ""),
                           "type": String(item.type || "int"),
                           "value": String(((skill.params || {})[item.field])
                                           === undefined ? ""
                                           : (skill.params || {})[item.field]) })
            }
        }
        return out
    }

    function routeEditStep(ctx, cellIndex) {
        if (!ctx)
            return
        ctx.editCell = Number(cellIndex)
        var cell = ctx.cells[ctx.editCell] || ({})
        ctx.editData = win.routeCopyCell(cell)
        ctx.editParams = win.routeEditParamsFor(cell)
        ctx.menu = ""
        ctx.menuCell = -1
        ctx.editLayer = true
        win.routeNotify(ctx)
    }

    // 卡片里改一个字段 → 写回这一格（存进 controller 的 routes）
    function routeEditSet(ctx, key, value) {
        if (!controller || ctx.editCell < 0)
            return
        var data = win.routeCopyCell(ctx.editData)
        if (key === "count") {
            var clean = String(value === undefined || value === null
                               ? "" : value).replace(/[^0-9]/g, "")
            data.count = clean === "" ? 1 : Math.max(1, Number(clean))
        } else if (key === "effect" || key === "name") {
            data[key] = String(value === undefined || value === null
                               ? "" : value)
        } else {
            data[key] = Number(String(value === undefined || value === null
                                      ? "" : value).replace(/[^0-9]/g, "") || 0)
        }
        controller.saveRouteCell(ctx.floor, ctx.index,
                                 ctx.editCell, data)
        ctx.editData = data
        win.routeSync(ctx)
        ctx.result = ({})
    }

    function routeEditSkill(ctx, skillIndex, field, value) {
        if (!controller || ctx.editCell < 0)
            return
        var data = win.routeCopyCell(ctx.editData)
        var skills = data.skills || []
        if (skillIndex < 0 || skillIndex >= skills.length)
            return
        var text = String(value === undefined || value === null ? "" : value)
        skills[skillIndex].params = skills[skillIndex].params || ({})
        skills[skillIndex].params[field] = text
        data.skills = skills
        controller.saveRouteCell(ctx.floor, ctx.index,
                                 ctx.editCell, data)
        var edit = ctx.editData || ({})
        var es = edit.skills || []
        if (es[skillIndex] !== undefined) {
            es[skillIndex].params = es[skillIndex].params || ({})
            es[skillIndex].params[field] = text
            edit.skills = es
        }
        win.routeSync(ctx)
        ctx.result = ({})
    }

    // 「删掉这步」（和伤害计算同一个按钮）：这一格回到"只是走过"
    // 「完成」：只关卡片、不改内容（「删掉这步」才真正清这一格）
    function routeEditDone(ctx) {
        if (!ctx)
            return
        ctx.editLayer = false
        ctx.editCell = -1
        ctx.editData = ({})
        ctx.editParams = []
        win.routeNotify(ctx)
    }

    function routeEditRemove(ctx) {
        if (!controller || ctx.editCell < 0)
            return
        controller.saveRouteCell(ctx.floor, ctx.index,
                                 ctx.editCell, {})
        ctx.editLayer = false
        ctx.editData = ({})
        ctx.editCell = -1
        win.routeSync(ctx)
        ctx.result = ({})
    }

    // 填进去：kind = monster / item / door；kind = "" = 清空这一格
    function routeFill(ctx, cellIndex, entry, kind) {
        if (!controller || !ctx)
            return
        var type = String(kind || "")
        var fill = ({})
        if (type === "monster" || type === "item") {
            fill = { "kind": type,
                     "name": String((entry || {}).name || ""),
                     "icon": String((entry || {}).icon || ""),
                     "effect": String((entry || {}).effect || ""),
                     "hp": Number((entry || {}).hp) || 0,
                     "atk": Number((entry || {}).atk) || 0,
                     "def": Number((entry || {}).def) || 0,
                     "skills": (entry || {}).skills || [] }
        } else if (type === "door") {
            fill = { "kind": "door" }
        }
        controller.saveRouteCell(ctx.floor, ctx.index,
                                 Number(cellIndex), fill)
        ctx.menu = ""
        ctx.menuCell = -1
        win.routeSync(ctx)
        ctx.result = ({})           // 链变了：上次算的结果作废
    }

    function routeRemove(ctx) {
        if (!controller || !ctx)
            return
        controller.removeRoute(ctx.floor, ctx.index)
        win.closeRoute(ctx)
    }

    // ---- 缓存下来的模型（Repeater 直接绑这些属性，避免每次重画都算一遍） ----
    property var monRows: []
    property var skills: []
    property var chats: []
    property var floorList: []
    property string monAgg: ""
    property string skillAgg: ""
    property string tower: ""
    property string notice: ""
    property string readTip: ""
    // 上次退出的会话记录提示（空 = 没有）
    property string sessionHint: ""

    function refreshFlash() {
        var tasks = (controller ? controller.tasks : null) || []
        var next = ({})
        var hasOk = false
        var hasErr = false
        for (var i = 0; i < tasks.length; i++) {
            var task = tasks[i] || {}
            var key = String(task.id)
            var prev = win.taskStates[key]
            next[key] = task.state
            if (task.state === "done" && prev !== "done")
                hasOk = true
            if (task.state === "failed" && prev !== "failed")
                hasErr = true
        }
        win.taskStates = next
        win.now = Date.now() / 1000
        win.refreshTasks()
        if (hasErr) {
            win.barFlash = "err"
            flashTimer.restart()
        } else if (hasOk) {
            win.barFlash = "ok"
            flashTimer.restart()
        }
    }

    property var taskStates: ({})
    // 读取记录（任务队列）：一行一条，跑着的显示跑了多久
    property var tasksView: []
    property real now: Date.now() / 1000

    Timer {
        id: flashTimer
        interval: 900
        repeat: false
        onTriggered: win.barFlash = ""
    }

    // 跑着的时候每秒刷一下 —— 记录行上的"12s"要动
    Timer {
        id: clockTimer
        interval: 1000
        repeat: true
        running: win.runningCount("map") + win.runningCount("monsters") > 0
        onTriggered: {
            win.now = Date.now() / 1000
            win.refreshTasks()
        }
    }


    // 两个「读取」：地图那栏只读地图，怪物那栏只读怪物手册（用户点名要分开）
    // 两个「读取」：地图那栏只读地图，怪物那栏只读怪物手册（用户点名要分开）。
    // **可以同时读**：每点一次起一条自己的任务，互不等待（并行读取是原来就有的能力）。
    function readMode(mode) {
        if (!controller)
            return
        win.readingMode = mode
        controller.readOnly(mode)
        win.refreshTasks()
    }

    // 某一栏现在有几条在跑（按钮上显示"读取中 N"）
    function runningCount(mode) {
        var total = 0
        var list = (controller ? controller.tasks : null) || []
        for (var i = 0; i < list.length; i++) {
            var task = list[i] || {}
            if (task.state === "running" && String(task.mode || "") === mode)
                total += 1
        }
        return total
    }

    // 读取记录：一行一条任务，跑着的能取消、失败的能重试
    function taskRows() {
        var rows = []
        var list = (controller ? controller.tasks : null) || []
        for (var i = 0; i < list.length; i++) {
            var task = list[i] || {}
            var state = String(task.state || "")
            var started = Number(task.started || 0)
            rows.push({
                id: task.id,
                state: state,
                text: String(task.text || ""),
                mode: String(task.mode || ""),
                modeLabel: String(task.mode || "") === "map" ? "地图"
                         : (String(task.mode || "") === "monsters" ? "手册"
                         : (String(task.mode || "") === "status" ? "人物" : "")),
                elapsed: (state === "running" && started > 0)
                         ? Math.max(0, Math.round(win.now - started)) : -1,
                // 这次读取用的截图：读的过程中/读完之后都留着（用户：
                // "读取用的截图怎么不显示了"）。src 是原图，url 是缩略图。
                url: String(task.url || ""),
                src: String(task.src || ""),
                canCancel: state === "running",
                canRetry: state === "failed"
            })
        }
        return rows
    }

    function refreshTasks() {
        win.tasksView = win.taskRows()
    }

    // ---- 地图的子界面：这一层到底有什么 ----
    function floorEntry(floorText) {
        if (!floorText)
            return null
        var list = win.floorEntries()
        for (var i = 0; i < list.length; i++) {
            if (String((list[i] || {}).floor || "") === floorText)
                return list[i]
        }
        return null
    }

    // ---- 地图的小窗：增删、移动、数据 ----
    // 地图块在窗口里的下沿（y）。用它决定小窗默认开在哪：别盖住地图本身。
    function mapGridBottom() {
        if (!flick || !body)
            return 0
        var limit = flick.y + flick.height
        return Math.min(body.mapBottom(), limit)
    }

    function openFloorSheet(floorText) {
        var name = String(floorText || "")
        if (name === "")
            return
        win.floorDeleteArm = false
        win.pickMode = ""
        // 已经开着就把它提到最上面（同一层不重复开）
        var rows = []
        var seen = false
        for (var i = 0; i < win.floorWindows.length; i++) {
            var item = String(win.floorWindows[i] || "")
            if (item === name) {
                seen = true
                continue
            }
            rows.push(item)
        }
        rows.push(name)
        // 头一次开：给个错开的位置，别让几扇窗严丝合缝叠在一起
        var positions = {}
        for (var key in win.floorPositions)
            positions[key] = win.floorPositions[key]
        // 只有"从没开过、也没存过位置"才给默认位置；关掉再开要回到上次的位置
        if (positions[name] === undefined) {
            // 默认贴着"地图块下沿"往下开、按顺序错开一点：上面那排地图块要留出来，
            // 不然第一扇窗一开就把地图盖住，第二块永远点不到（也就没法多开）。
            // 小窗现在是**真窗口**，坐标要换成屏幕坐标：主窗口在哪就开在它旁边。
            var offset = Math.min(3, rows.length - 1) * 10
            var bottom = win.mapGridBottom()
            var fallback = Math.max(8, win.height - 404)
            positions[name] = { x: Math.round(win.x + 8 + offset),
                                y: Math.round(win.y
                                    + Math.max(8, Math.min(bottom + 8, fallback))) }
        }
        win.floorPositions = positions
        win.floorWindows = rows
        if (seen) {
            // 这一层已经开着：把它**提到最前面**（用户："我不关闭小窗再点地图没反应，
            // 应该把对应窗口前置"）。以前只是把它挪到列表末尾，窗口不会浮上来。
            var opened = win.floorSheetOf(name)
            if (opened) {
                try {
                    opened.show()
                    opened.raise()
                    opened.requestActivate()
                } catch (error) {}
            }
        }
    }

    function closeFloorSheet(floorText) {
        var name = String(floorText || win.openFloor || "")
        var rows = []
        for (var i = 0; i < win.floorWindows.length; i++) {
            var item = String(win.floorWindows[i] || "")
            if (item === name)
                continue
            rows.push(item)
        }
        win.floorWindows = rows
        win.pickMode = ""
        win.floorDeleteArm = false
        // 关掉正在编辑的那一层：编辑模式一起退出
        //（用户："开启编辑功能再关闭窗口后再次开启窗口依然是编辑功能开启的状态"）
        if (win.gridEditOn && win.gridEditFloor === name) {
            win.gridEditOn = false
            win.gridEditFloor = ""
            win.gridHover = ({})
            win.gridDrag = ({})
            win.gridSelected = ""
            win.gridMulti = []
        }
    }

    // 主窗口要关了：小窗全收掉（Qt.Tool 窗口不跟着主窗口走，不收掉进程会留着）
    function closeAllSheets() {
        win.floorWindows = []
        win.pickMode = ""
        win.gridEditOn = false
        win.gridEditFloor = ""
        win.gridHover = ({})
        win.gridDrag = ({})
        win.gridSelected = ""
        win.gridMulti = []
        var map = win.floorSheets
        for (var name in map) {
            var sheet = map[name]
            if (sheet) {
                try { sheet.destroy() } catch (error) {}
            }
        }
        win.floorSheets = ({})
    }

    // fit 的名字 → 真窗口对象（没有就是 null）
    function floorSheetOf(floorText) {
        return win.floorSheets[String(floorText || "")] || null
    }

    // 名字列表和真窗口对齐：多的开出来、少的收掉（重复调用没副作用）
    function syncFloorSheets() {
        var want = {}
        for (var i = 0; i < win.floorWindows.length; i++) {
            var key = String(win.floorWindows[i] || "")
            if (key !== "")
                want[key] = true
        }
        var map = {}
        var changed = false
        for (var old in win.floorSheets) {
            if (want[old]) {
                map[old] = win.floorSheets[old]
                continue
            }
            changed = true
            var gone = win.floorSheets[old]
            if (gone) {
                try { gone.destroy() } catch (error) {}
            }
        }
        if (floorSheetWindow.status !== Component.Ready)
            return
        for (var name in want) {
            if (map[name])
                continue
            var position = win.floorPositions[name] || ({})
            var sheet = floorSheetWindow.createObject(null, {
                "sheetName": name,
                "x": position.x !== undefined ? position.x : Math.round(win.x + 8),
                "y": position.y !== undefined ? position.y : Math.round(win.y + 8)
            })
            if (!sheet)
                continue
            map[name] = sheet
            changed = true
            sheet.clampPos()
            sheet.show()
        }
        if (changed)
            win.floorSheets = map
    }

    // 关最上面那个（Esc / 点遮罩）
    // 打开"下一层还没开的那扇窗"（循环找，找不到就什么都不做）
    function openNextFloor(floorText) {
        var list = win.floorList
        var current = -1
        for (var i = 0; i < list.length; i++) {
            if (String((list[i] || {}).floor || "") === String(floorText || ""))
                current = i
        }
        for (var step = 1; step <= list.length; step++) {
            var entry = list[(current + step + list.length) % list.length] || {}
            var next = String(entry.floor || "")
            if (next !== "" && win.floorWindows.indexOf(next) < 0) {
                win.openFloorSheet(next)
                return
            }
        }
    }

    function closeTopFloorWindow() {
        win.closeFloorSheet(win.openFloor)
    }

    // ---- 伤害计算（用户："做一个伤害计算的功能"）----
    // 入口是导航条上的 ⚔：它是一扇自己的窗口，可以摆在游戏窗口旁边边打边算。
    // 人物数值默认从状态行带出来（"根据人物的当前状态计算掉血"），也可以手改。
    //
    // 2026-10-27 第 5 次返工后的形状（用户："一行！！！"）：**一次计算就是一整行**，
    // 横向排成一条链：勇者 → 怪 −930 → 红宝石 +2攻 → 怪 −2万 …；点「计算」把掉血
    // 写在每个怪后面；想比不同顺序，就「＋ 新的计算」再摆一行，两行的总掉血对着看。
    property var battleWindow: null
    // 一行一个计划：`[{"steps": [step, step, ...]}, ...]`
    property var battlePlans: []
    // 每行算完的结果（`controller.computeBattle` 那份），按下标对齐
    property var battlePlanResults: []
    // 给 Repeater 用的副本：列表直接读它，不去读 battlePlans
    //（写在绑定里读会报 "Binding loop detected"）
    property var battleRows: []
    // 一次「计算」里最省的那一行（-1 = 还没算）
    property int battleBestPlan: -1
    property var battleHero: ({ "hp": 0, "atk": 0, "def": 0, "mdef": 0 })
    // 结果过期了（改了东西还没点「计算」）：用户要的是"点计算后出结果"
    property bool battleDirty: true
    // 一行最少这么高（链折行以后这一行会自己长高）
    readonly property int battleRowH: 26
    readonly property int battleRowGap: 4
    // 链上一格的大小：点这一格改数值；链尾那格是问号（接着加）
    // 用户："怪物和资源得缩略图太大了" → 20 收到 14（和状态行的图标一个量级）
    readonly property int battleSlotW: 14
    readonly property int battleAskW: 16
    // 用户拉过的大小（0 = 还没拉过，跟着内容自适应）
    property real battleWinW: 0
    property real battleWinH: 0
    // 点缩略图改参数那一层
    property bool battleEditLayer: false
    property int battleEditPlan: -1
    property int battleEditStepIndex: -1
    // 正在编辑的那一步的副本：编辑器直接读它（读列表里的那份会被 QML 当成循环绑定）
    property var battleEditData: ({})
    // 编辑器的技能参数行：算好放在属性里（写成函数调用当 model 会报循环绑定）
    property var battleEditParams: []
    // 问号点开的下拉菜单：两个标签页（怪物 / 资源），挂在那一行下面
    property string battleMenu: ""
    property int battleMenuPlan: -1
    // 下一条插在第几格前面（-1 = 接在最后）
    property int battleMenuInsert: -1
    property string battlePickTab: "monster"
    property var battlePickData: []
    property real battleMenuX: 0
    property real battleMenuY: 0
    property int battleMenuRows: 8

    function openBattle() {
        if (!win.battleWindow) {
            win.battleWindow = battleWindowComp.createObject(null, {})
            if (!win.battleWindow)
                return
        }
        // 人物当前状态：从状态行带出来（读不到就是 0，用户自己填）
        var hero = controller ? controller.battleHero() : null
        var next = { hp: 0, atk: 0, def: 0, mdef: 0 }
        if (hero) {
            for (var key in next)
                next[key] = Number(hero[key] || 0)
        }
        win.battleHero = next
        win.battleMenu = ""
        win.battleMenuPlan = -1
        // 一行都没有就先摆一行"勇者 → ?"，点问号就能开始
        if (win.battlePlans.length === 0)
            win.battleAddPlan()
        win.battleWindow.place()
        win.battleWindow.show()
        win.battleMarkDirty()
    }

    function closeBattle() {
        win.battleMenu = ""
        if (win.battleWindow) {
            var gone = win.battleWindow
            win.battleWindow = null
            gone.destroy()
        }
    }

    // ---- 路线对比：把几条算好的路线摆一起，比每只怪掉多少血 ----
    property var compareWindow: null
    property real compareWinW: 0
    property real compareWinH: 0
    // 每条 = { label, steps, result }（result 是 computeBattle 那一份）
    property var compareRoutes: []
    // 对比表点了哪一行 → 地图上圈这一格（用户："点击后会在地图内高亮"）。
    // 三个真属性，不是对象：对象改了不会通知 QML 的绑定（踩过）。
    property string mapHiFloor: ""
    property int mapHiRow: -1
    property int mapHiCol: -1

    function openCompare() {
        if (!win.compareWindow) {
            win.compareWindow = compareWindowComp.createObject(null, {})
            if (!win.compareWindow)
                return
        }
        win.compareWindow.place()
        win.compareWindow.show()
        try {
            win.compareWindow.raise()
            win.compareWindow.requestActivate()
        } catch (error) {}
    }

    function closeCompare() {
        win.mapHiFloor = ""
        win.mapHiRow = -1
        win.mapHiCol = -1
        if (win.compareWindow) {
            var gone = win.compareWindow
            win.compareWindow = null
            gone.destroy()
        }
    }

    // 对比表点一行 = 它的坐标：开那一层的小窗（已开着就提到前面）并圈出这一格。
    // 坐标不全是空的老路线（手粘的 JSON）就什么都不做，返回 false。
    function compareHighlight(spot) {
        var at = spot || ({})
        var floor = String(at.floor || "")
        var row = Number(at.row)
        var col = Number(at.col)
        if (floor === "" || !isFinite(row) || !isFinite(col)
                || row < 0 || col < 0)
            return false
        win.mapHiFloor = floor
        win.mapHiRow = Math.round(row)
        win.mapHiCol = Math.round(col)
        win.openFloorSheet(floor)
        return true
    }

    // 加一条路线（steps 已经是「伤害计算」那套步骤），顺手按当前人物状态算一遍
    function compareAdd(steps, label) {
        if (!controller || !steps || steps.length === 0)
            return -1
        var hero = controller.battleHero() || ({})
        var result = controller.computeBattle(JSON.stringify({
            "hero": hero, "steps": steps })) || ({})
        var routes = win.compareRoutes.slice(0)
        var name = String(label || "")
        if (name === "")
            name = "路线" + (routes.length + 1)
        routes.push({ "label": name, "steps": steps, "result": result })
        win.compareRoutes = routes
        return routes.length - 1
    }

    // 从系统剪贴板导入一条（和伤害计算「粘贴」同一种 JSON）
    function comparePaste() {
        if (!controller)
            return
        var steps = win.routeParseClipboard(controller.clipboardText())
        if (steps.length === 0)
            return
        win.compareAdd(steps, "")
        win.openCompare()
    }

    // 拖进来的路线（路线链上那个「拖」把同样的 JSON 塞进 mimeData）
    function compareDropRoute(text) {
        if (!controller)
            return
        var steps = win.routeParseClipboard(String(text || ""))
        if (steps.length === 0)
            return
        win.compareAdd(steps, "")
        win.openCompare()
    }

    function compareRemove(index) {
        var routes = win.compareRoutes.slice(0)
        if (index < 0 || index >= routes.length)
            return
        routes.splice(index, 1)
        win.compareRoutes = routes
    }

    function compareClear() {
        win.compareRoutes = []
        win.mapHiFloor = ""
        win.mapHiRow = -1
        win.mapHiCol = -1
    }

    // 对比表：行 = 一只怪（按「名字 + 第几只」对齐），列 = 各路线。
    // 行的**显示**只认缩略图 + 坐标（用户："不要写怪物名字！！！用缩略图和坐标！！"），
    // 名字只留着对齐（同一条路线里可能有两只同名怪）和没图时当占位字。
    function compareRows() {
        var routes = win.compareRoutes || []
        var keys = []
        var info = ({})
        var perRoute = []
        for (var r = 0; r < routes.length; r++) {
            var steps = routes[r].steps || []
            var rows = (routes[r].result || ({})).rows || []
            var seen = ({})
            var map = ({})
            for (var i = 0; i < steps.length; i++) {
                var step = steps[i] || ({})
                if (String(step.kind || "") !== "monster")
                    continue
                var name = String(step.name || "")
                seen[name] = (seen[name] || 0) + 1
                var key = name + "#" + seen[name]
                var row = rows[i] || ({})
                map[key] = { "damage": row.damage === undefined ? null
                                                           : row.damage,
                             "lethal": !!row.lethal,
                             "bad": row.ok === false }
                if (info[key] === undefined) {
                    info[key] = { "name": name, "occurrence": seen[name],
                                  "icon": "", "floor": "",
                                  "row": -1, "col": -1 }
                    keys.push(key)
                }
                // 坐标/图标取**第一条带它们的路线**：同一条路线的同一只怪，
                // 层和格是同一个；老数据（没坐标）就往后找，找不到就空着
                var slot = info[key]
                if (String(slot.icon || "") === "")
                    slot.icon = String(step.icon || "")
                if (String(slot.floor || "") === "")
                    slot.floor = String(step.floor || "")
                if (Number(slot.row) < 0 && isFinite(Number(step.row)))
                    slot.row = Math.round(Number(step.row))
                if (Number(slot.col) < 0 && isFinite(Number(step.col)))
                    slot.col = Math.round(Number(step.col))
            }
            perRoute.push(map)
        }
        var out = []
        for (var k = 0; k < keys.length; k++) {
            var key2 = keys[k]
            var damages = []
            for (var c = 0; c < routes.length; c++)
                damages.push(perRoute[c][key2] === undefined
                             ? null : perRoute[c][key2])
            out.push({ "key": key2, "name": info[key2].name,
                       "occurrence": info[key2].occurrence,
                       "icon": info[key2].icon, "floor": info[key2].floor,
                       "row": info[key2].row, "col": info[key2].col,
                       "damages": damages })
        }
        return out
    }

    // 每条路线的合计：总掉血 / 剩血
    function compareTotals() {
        var routes = win.compareRoutes || []
        var out = []
        for (var i = 0; i < routes.length; i++) {
            var res = routes[i].result || ({})
            out.push({ "total": res.total_damage,
                       "hp": res.hp_after,
                       "dead": res.hp_after !== undefined
                               && Number(res.hp_after) <= 0 })
        }
        return out
    }

    // 大数字按游戏里的写法显示（21000万 / 1.2亿），一眼看得出量级
    function fmt(value) {
        var number = Number(value)
        if (value === null || value === undefined || !isFinite(number))
            return "-"
        var abs = Math.abs(number)
        var unit = ""
        var scale = 1
        if (abs >= 100000000) {
            unit = "亿"
            scale = 100000000
        } else if (abs >= 10000) {
            unit = "万"
            scale = 10000
        }
        if (scale === 1)
            return String(Math.round(number))
        var text = (number / scale).toFixed(2)
        // 只砍"没有意义的小数零"：2.04 不能被砍成 24
        text = text.replace(/0+$/, "").replace(/\.$/, "")
        return text + unit
    }

    // 编辑器里要画的"技能参数格里的一行"：把各技能的 schema 摊平
    function battleParamRows(step) {
        var out = []
        var skills = (step || {}).skills || []
        for (var i = 0; i < skills.length; i++) {
            var skill = skills[i] || ({})
            var schema = skill.schema || []
            for (var j = 0; j < schema.length; j++) {
                var item = schema[j] || ({})
                out.push({ "skillIndex": i,
                           "skillName": String(skill.name || ""),
                           "field": String(item.field || ""),
                           "label": String(item.label || item.field || ""),
                           "unit": String(item.unit || ""),
                           "type": String(item.type || "int"),
                           "value": String((((skill.params || {})[item.field])
                                            === undefined
                                            ? "" : (skill.params || {})[item.field])) })
            }
        }
        return out
    }

    // 这一步的图：怪用手册里的图标，资源用 assets/items 里的图
    function battleStepIcon(step) {
        var icon = String((step || {}).icon || "")
        if (icon === "")
            return ""
        if (String((step || {}).kind || "") === "item")
            return win.itemIcon(icon)
        return icon
    }

    function battleSetHero(key, text) {
        var next = {}
        for (var name in win.battleHero)
            next[name] = win.battleHero[name]
        var clean = String(text === undefined || text === null ? "" : text)
            .replace(/[^0-9]/g, "")
        next[key] = clean === "" ? 0 : Number(clean)
        win.battleHero = next
        win.battleMarkDirty()
    }

    // 计划 → 列表用的副本（每行 = 勇者 + 一串东西）
    function battleSyncRows() {
        var plans = win.battlePlans || []
        var rows = []
        for (var i = 0; i < plans.length; i++)
            rows.push({ "index": i, "steps": (plans[i] || {}).steps || [] })
        win.battleRows = rows
    }

    // 「＋ 新的计算」：多开一行（用户："一个按钮创建新的计算"）
    function battleAddPlan() {
        var plans = win.battlePlans.slice(0)
        plans.push({ "steps": [] })
        win.battlePlans = plans
        win.battleMenu = ""
        win.battleMenuPlan = -1
        win.battleMenuInsert = -1
        win.battleSyncRows()
        win.battleMarkDirty(plans.length - 1)
    }

    // 「粘贴」：从系统剪贴板读回路线（「复制」时写的是 JSON），摆成一行新计算
    //（用户："路线要能复制，可以粘贴到伤害计算界面"）
    function battlePaste() {
        if (!controller)
            return
        var steps = win.routeParseClipboard(controller.clipboardText())
        if (steps.length === 0)
            return
        var plans = win.battlePlans.slice(0)
        plans.push({ "steps": steps })
        win.battlePlans = plans
        win.battleMenu = ""
        win.battleMenuPlan = -1
        win.battleMenuInsert = -1
        win.battleSyncRows()
        win.battleMarkDirty(plans.length - 1)
    }

    function battleRemovePlan(planIndex) {
        var plans = win.battlePlans.slice(0)
        if (planIndex < 0 || planIndex >= plans.length)
            return
        plans.splice(planIndex, 1)
        win.battlePlans = plans
        var results = (win.battlePlanResults || []).slice(0)
        results.splice(planIndex, 1)
        win.battleMenu = ""
        win.battleMenuPlan = -1
        win.battleMenuInsert = -1
        win.battleEditLayer = false
        win.battleSyncRows()
        win.battleSetResults(results)
    }

    // 这一行算完的结果（改过/没算过就是空）
    function battlePlanResult(planIndex) {
        if (planIndex < 0)
            return ({})
        var results = win.battlePlanResults || []
        return results[planIndex] || ({})
    }

    // 这一行算过没有（用户："每一条要能单独计算"）
    function battlePlanComputed(planIndex) {
        return win.battlePlanResult(planIndex).total_damage !== undefined
    }

    // 这一行里第几步的结果
    function battleStepResult(planIndex, stepIndex) {
        var result = win.battlePlanResult(planIndex)
        var rows = result.rows || []
        return rows[stepIndex] || ({})
    }

    // 链尾的"总掉血 / 剩血"：一行一个
    function battlePlanTotal(planIndex) {
        var result = win.battlePlanResult(planIndex)
        if (result.total_damage === undefined)
            return ""
        var text = "总掉血 " + win.fmt(result.total_damage)
        if (win.battleRows.length > 1 && win.battleBestPlan === planIndex)
            text = "✔ " + text
        return text
    }

    function battlePlanLeft(planIndex) {
        var result = win.battlePlanResult(planIndex)
        if (result.hp_after === undefined)
            return ""
        return "剩血 " + win.fmt(result.hp_after)
    }

    // 掉血最少的那一行（只在算过的行里挑）
    function battleFindBest(results) {
        var best = -1
        var least = 0
        for (var i = 0; i < (results || []).length; i++) {
            var row = results[i] || ({})
            if (row.total_damage === undefined)
                continue
            var total = Number(row.total_damage)
            if (best < 0 || total < least) {
                best = i
                least = total
            }
        }
        return best
    }

    function battleAllComputed(results) {
        var plans = win.battlePlans || []
        if (plans.length === 0)
            return false
        for (var i = 0; i < plans.length; i++) {
            var row = (results || [])[i] || ({})
            if (row.total_damage === undefined)
                return false
        }
        return true
    }

    function battleSetResults(results) {
        win.battlePlanResults = results || []
        win.battleBestPlan = win.battleFindBest(results)
        win.battleDirty = !win.battleAllComputed(results)
    }

    // 改了东西 → 结果作废：不给行号就是全部作废（比如改了人物数值）
    function battleMarkDirty(planIndex) {
        var results = (win.battlePlanResults || []).slice(0)
        if (planIndex === undefined || planIndex === null || planIndex < 0) {
            for (var i = 0; i < results.length; i++)
                results[i] = ({})
        } else if (planIndex < results.length) {
            results[planIndex] = ({})
        }
        win.battleSyncRows()
        win.battleSetResults(results)
    }

    // 选中了怪/资源：insertAt = 插在第几格前面（-1 = 接在最后）
    // （用户："点箭头要能插入"）
    function battleFillRow(planIndex, entry, kind, insertAt) {
        var plans = win.battlePlans.slice(0)
        if (!entry || planIndex < 0 || planIndex >= plans.length)
            return
        var steps = ((plans[planIndex] || {}).steps || []).slice(0)
        var step = ({})
        if (String(kind) === "item") {
            step = { "kind": "item", "name": String(entry.name || ""),
                     "effect": String(entry.effect || ""),
                     "icon": String(entry.icon || ""), "count": 1 }
        } else {
            step = { "kind": "monster", "name": String(entry.name || ""),
                     "hp": Number(entry.hp) || 0,
                     "atk": Number(entry.atk) || 0,
                     "def": Number(entry.def) || 0,
                     "icon": String(entry.icon || ""), "count": 1,
                     "skills": entry.skills || [],
                     "skillsText": String(entry.skillsText || "") }
        }
        var at = Number(insertAt)
        if (!isFinite(at) || at < 0 || at > steps.length)
            at = steps.length
        steps.splice(at, 0, step)
        plans[planIndex] = { "steps": steps }
        win.battlePlans = plans
        win.battleMenu = ""
        win.battleMenuPlan = -1
        win.battleMenuInsert = -1
        win.battleMarkDirty(planIndex)
    }

    // 只算这一行（用户："每一条要能单独计算"）
    function battleComputePlan(planIndex) {
        if (!controller || !win.battleWindow)
            return
        var plans = win.battlePlans || []
        if (planIndex < 0 || planIndex >= plans.length)
            return
        var payload = JSON.stringify({
            "hero": win.battleHero,
            "steps": (plans[planIndex] || {}).steps || [] })
        var results = (win.battlePlanResults || []).slice(0)
        while (results.length < plans.length)
            results.push(({}))
        results[planIndex] = controller.computeBattle(payload) || ({})
        win.battleSetResults(results)
    }

    // 点缩略图改参数（血量/攻击/防御/数量、资源的效果、技能参数）
    function battleEditStep(planIndex, stepIndex) {
        var steps = ((win.battlePlans || [])[planIndex] || {}).steps || []
        if (planIndex < 0 || stepIndex < 0 || stepIndex >= steps.length)
            return
        win.battleEditPlan = planIndex
        win.battleEditStepIndex = stepIndex
        win.battleEditData = win.battleCopyStep(planIndex, stepIndex)
        win.battleEditParams = win.battleParamRows(win.battleEditData)
        win.battleEditLayer = true
    }

    // 深一点地复制一步（技能和参数也要复制，改参数时不能动到原来那份）
    function battleCopyStep(planIndex, stepIndex) {
        var step = {}
        var source = (((win.battlePlans || [])[planIndex] || {}).steps
                      || [])[stepIndex] || ({})
        for (var name in source)
            step[name] = source[name]
        var skills = []
        var list = source.skills || []
        for (var i = 0; i < list.length; i++) {
            var item = list[i] || ({})
            var copy = {}
            for (var key in item)
                copy[key] = item[key]
            var params = {}
            for (var field in (item.params || {}))
                params[field] = item.params[field]
            copy.params = params
            skills.push(copy)
        }
        step.skills = skills
        return step
    }

    function battleSetStep(planIndex, stepIndex, key, value) {
        var plans = (win.battlePlans || []).slice(0)
        var steps = ((plans[planIndex] || {}).steps || []).slice(0)
        if (planIndex < 0 || stepIndex < 0 || stepIndex >= steps.length)
            return
        var step = win.battleCopyStep(planIndex, stepIndex)
        if (key === "count") {
            var clean = String(value === undefined || value === null ? "" : value)
                .replace(/[^0-9]/g, "")
            step.count = clean === "" ? 1 : Math.max(1, Number(clean))
        } else if (key === "effect" || key === "name") {
            step[key] = String(value === undefined || value === null
                               ? "" : value)
        } else {
            step[key] = Number(String(value === undefined || value === null
                                      ? "" : value).replace(/[^0-9]/g, "") || 0)
        }
        steps[stepIndex] = step
        plans[planIndex] = { "steps": steps }
        win.battlePlans = plans
        win.battleEditData = step
        win.battleMarkDirty(planIndex)
    }

    function battleSetSkillParam(planIndex, stepIndex, skillIndex, field, value) {
        var plans = (win.battlePlans || []).slice(0)
        var steps = ((plans[planIndex] || {}).steps || []).slice(0)
        if (planIndex < 0 || stepIndex < 0 || stepIndex >= steps.length)
            return
        var text = String(value === undefined || value === null ? "" : value)
        // 原地改：不换 battleEditParams（一换 Repeater 就重建，QML 会报绑定循环）
        var step = steps[stepIndex] || ({})
        var skills = step.skills || []
        if (skillIndex < 0 || skillIndex >= skills.length) {
            return
        }
        var params = skills[skillIndex].params || ({})
        params[field] = text
        skills[skillIndex].params = params
        step.skills = skills
        steps[stepIndex] = step
        plans[planIndex] = { "steps": steps }
        win.battlePlans = plans
        var edit = win.battleEditData || ({})
        var editSkills = edit.skills || []
        if (editSkills[skillIndex] !== undefined) {
            editSkills[skillIndex].params[field] = text
            edit.skills = editSkills
        }
        win.battleMarkDirty(planIndex)
    }

    // 从状态行读一次"当前状态"（用户："不能读取当前状态"）
    function battlePullHero() {
        if (!controller)
            return
        var hero = controller.battleHero()
        var next = { hp: 0, atk: 0, def: 0, mdef: 0 }
        if (hero) {
            for (var key in next)
                next[key] = Number(hero[key] || 0)
        }
        win.battleHero = next
        win.battleMarkDirty()
    }

    // 编辑器里的「删除这步」
    function battleRemoveStep(planIndex, stepIndex) {
        var plans = (win.battlePlans || []).slice(0)
        var steps = ((plans[planIndex] || {}).steps || []).slice(0)
        if (planIndex < 0 || stepIndex < 0 || stepIndex >= steps.length)
            return
        steps.splice(stepIndex, 1)
        plans[planIndex] = { "steps": steps }
        win.battlePlans = plans
        win.battleEditLayer = false
        win.battleEditData = ({})
        win.battleMarkDirty(planIndex)
    }

    // 编辑卡片里的三个回调（卡片只知道"正在编辑的那一步"）
    function battleEditSet(key, value) {
        win.battleSetStep(win.battleEditPlan, win.battleEditStepIndex, key, value)
    }

    function battleEditSkill(skillIndex, field, value) {
        win.battleSetSkillParam(win.battleEditPlan, win.battleEditStepIndex,
                                skillIndex, field, value)
    }

    function battleEditRemove() {
        win.battleRemoveStep(win.battleEditPlan, win.battleEditStepIndex)
    }

    function battleClear() {
        win.battlePlans = []
        win.battlePlanResults = []
        win.battleBestPlan = -1
        win.battleDirty = true
        win.battleMenu = ""
        win.battleMenuPlan = -1
        win.battleMenuInsert = -1
        win.battleSyncRows()
    }

    // 问号点开的菜单：**两个标签页**——怪物 / 资源（用户："应该只有两个标签页
    // 分别是怪物和资源（包含 4 色宝石）"）。以前把怪和 76 条资源摆成一个长列表，
    // 大半是书/证明这种跟掉血无关的东西。
    // insertAt = 插在第几格前面（-1 = 接在最后；点箭头进来时带具体位置）
    function openBattleMenu(planIndex, insertAt) {
        win.battleMenuPlan = planIndex
        win.battleMenuInsert = (insertAt === undefined || insertAt === null)
                               ? -1 : Number(insertAt)
        win.battleMenu = "any"
        win.battlePickTab = "monster"
        win.battleRefreshPick()
    }

    function battleSwitchTab(tab) {
        if (win.battlePickTab === tab)
            return
        win.battlePickTab = tab
        win.battleRefreshPick()
    }

    function battleRefreshPick() {
        // 条目算好放进属性：写成函数调用当 model 会报循环绑定
        win.battlePickData = win.battlePickRows()
        win.battleMenuRows = win.battlePickData.length
        win.battleMenuPlace()
        Qt.callLater(win.battleMenuPlace)
    }

    // 当前标签页的条目（带 kind：选中的时候要分辨）
    function battlePickRows() {
        var out = []
        if (win.battlePickTab === "item") {
            var items = controller ? controller.battleItems() : []
            for (var i = 0; i < items.length; i++)
                out.push({ "kind": "item", "entry": items[i] })
            return out
        }
        var mons = controller ? controller.battleMonsters() : []
        for (var j = 0; j < mons.length; j++)
            out.push({ "kind": "monster", "entry": mons[j] })
        return out
    }

    function battleMenuPlace() {
        if (win.battleWindow && win.battleWindow.placeMenu)
            win.battleWindow.placeMenu()
    }

    // 给脚本/预览用的老入口：接在最后一行后面
    function battleAddMonster(entry) {
        if (win.battlePlans.length === 0)
            win.battleAddPlan()
        win.battleFillRow(win.battlePlans.length - 1, entry, "monster")
    }

    function battleAddItem(entry) {
        if (win.battlePlans.length === 0)
            win.battleAddPlan()
        win.battleFillRow(win.battlePlans.length - 1, entry, "item")
    }

    // 小窗位置是**屏幕坐标**（真窗口），不是主窗口里的坐标
    function floorX(floorText) {
        var row = win.floorPositions[String(floorText || "")]
        return row && row.x !== undefined ? row.x : Math.round(win.x + 8)
    }

    function floorY(floorText) {
        var row = win.floorPositions[String(floorText || "")]
        return row && row.y !== undefined ? row.y : Math.round(win.y + 8)
    }

    // 拖完把位置记下来（不动 floorWindows，窗口不会重建）
    function saveFloorPos(floorText, x, y) {
        var name = String(floorText || "")
        var positions = {}
        for (var key in win.floorPositions)
            positions[key] = win.floorPositions[key]
        positions[name] = { x: Math.round(x), y: Math.round(y) }
        win.floorPositions = positions
    }

    // ---- 地图小窗的大小（用户："怎么不能放大"） ----
    function floorW(floorText, fallback) {
        var row = win.floorSizes[String(floorText || "")]
        return row && row.w !== undefined ? row.w : fallback
    }

    function floorH(floorText, fallback) {
        var row = win.floorSizes[String(floorText || "")]
        return row && row.h !== undefined ? row.h : fallback
    }

    function saveFloorSize(floorText, w, h) {
        var name = String(floorText || "")
        if (name === "")
            return
        var sizes = {}
        for (var key in win.floorSizes)
            sizes[key] = win.floorSizes[key]
        sizes[name] = { w: Math.round(w), h: Math.round(h) }
        win.floorSizes = sizes
    }

    function sheetMons(floorText) {
        var entry = win.floorEntry(floorText)
        return entry ? (entry.mons || []) : []
    }

    function sheetItems(floorText) {
        var entry = win.floorEntry(floorText)
        return entry ? (entry.items || []) : []
    }

    function sheetShot(floorText) {
        var entry = win.floorEntry(floorText)
        return entry ? String(entry.url || "") : ""
    }

    function sheetMemo(floorText) {
        var entry = win.floorEntry(floorText)
        return entry ? String(entry.memo || "") : ""
    }

    // 加怪候选：手册里的怪 + 地图上出现过的名字（同一座塔里能加的都在）
    function monChoices() {
        var out = []
        var seen = {}
        var db = (controller ? controller.monsters : null) || []
        for (var i = 0; i < db.length; i++) {
            var m = db[i] || {}
            var name = String(m.name || "").trim()
            if (name === "" || seen[name])
                continue
            seen[name] = true
            out.push({ name: name, icon: m.icon || "" })
        }
        var names = (controller ? controller.mapMonsterNames : null) || []
        for (var j = 0; j < names.length; j++) {
            var other = String(names[j] || "").trim()
            if (other === "" || seen[other])
                continue
            seen[other] = true
            out.push({ name: other, icon: win.monsterIconNamed(other) })
        }
        return out
    }

    function itemChoices() {
        return (controller ? controller.itemChoices() : null) || []
    }

    // 名字 → 图标：手册里记过这只怪就用它的图（加怪列表、本层清单都用得上）
    function monsterIconNamed(name) {
        // 先看这次读手册有没有这只怪（手册抠下来的那张图最准），
        // 再退回素材库按名字找（两座新新魔塔的图）。
        var db = (controller ? controller.monsters : null) || []
        for (var i = 0; i < db.length; i++) {
            if (String((db[i] || {}).name || "") === String(name || "")
                    && win.hasUrl((db[i] || {}).icon))
                return String((db[i] || {}).icon || "")
        }
        return controller ? String(controller.libraryIconByName(String(name || "")) || "")
                         : ""
    }

    function itemIcon(name) {
        // 资源图标在 assets/items（itemBase），不在 assets/icons —— 用错目录会是空图。
        // `name` 两种都可能：素材名（potion_red）或 AI 裁下来的**临时文件 URL**
        // （手册/地图读回来就是 URL）。以前无脑拼 itemBase，URL 被拼成
        // "file:///<items>/file:///..." 必然打不开 —— 用户："资源的缩略图怎么没有了"。
        if (!win.itemBase || !name)
            return ""
        var text = String(name)
        if (text.indexOf("file:") === 0 || text.indexOf("/") === 0
                || /^[A-Za-z]:[\\/]/.test(text))
            return text
        return win.itemBase + text + ".png"
    }

    // 资源的效果拆三截：属性（道具表写死）、符号（写死）、数量（可以改）。
    // 用户："宝石加的属性要写死，加的数值要能改"、"我说的是「攻击力」三个字"、
    // "怎么加号不是固定的？"。
    function effectLabel(text) {
        return controller ? String(controller.itemEffectLabel(String(text || "")) || "")
                         : ""
    }

    function effectValue(text) {
        return controller ? String(controller.itemEffectValue(String(text || "")) || "")
                         : ""
    }

    // {label, sign, digits}：拆法在 Python（iteminfo.split_effect），这里只转发
    function effectParts(text) {
        if (!controller)
            return { "label": "", "sign": "", "digits": "" }
        var parts = controller.itemEffectParts(String(text || "")) || ({})
        return {
            "label": String(parts.label || ""),
            "sign": String(parts.sign || ""),
            "digits": String(parts.digits || "")
        }
    }

    // ---- 加怪 / 加资源：挂在「＋」按钮下面的下拉菜单 ----
    function openPickMenu(mode, floorText, button, replaceIndex, host) {
        win.pickFloor = String(floorText || win.openFloor || "")
        win.pickAnchor = button || null
        win.pickHost = host || null
        win.pickReplaceIndex = (replaceIndex === undefined || replaceIndex === null)
                                ? -1 : Number(replaceIndex)
        win.pickMode = mode
        // 先按按钮现在的位置摆一次：等 callLater 再摆的话，菜单会先闪在左上角，
        // 这一瞬间点下去点到的是空白（实测过：菜单还挂在 0,0 时点行没反应）
        win.placePickMenu()
        Qt.callLater(win.placePickMenu)   // 列表长出来后高度变了，再量一次
    }

    function placePickMenu() {
        if (win.pickMode === "")
            return
        var anchor = win.pickAnchor
        if (!anchor)
            return
        // 菜单层铺满的是"小窗"（anchor 所在的那个窗口），坐标就是那个窗口里的坐标
        var host = win.pickHost
        var hostW = host ? host.width : win.width
        var hostH = host ? host.height : win.height
        var menuW = 208
        var rows = win.pickMode === "mon" ? win.monChoices().length
                                          : win.itemChoices().length
        var point = anchor.mapToItem(null, 0, anchor.height + 4)
        var anchorTop = point.y - anchor.height - 4
        // 小窗很矮的时候（用户："窗口小的时候加资源的下拉菜单显示不全"）：
        // 上下哪边空间大就放哪边，列表高度按那边的空间收，最后再整块钳回窗口里 ——
        // 不然卡片会被窗口边缘裁掉，下半截根本看不到。
        var below = Math.max(0, hostH - point.y - 6)
        var above = Math.max(0, anchorTop - 6)
        var useBelow = below >= above
        var space = Math.max(40, useBelow ? below : above)
        var listMax = Math.max(56, Math.min(240, space - 34))
        win.pickListMax = listMax
        var height = 26 + Math.min(listMax, Math.max(1, rows) * 28) + 8
        var top = useBelow ? point.y : Math.max(4, anchorTop - height)
        win.pickMenuX = Math.max(4, Math.min(hostW - 8 - menuW, point.x))
        win.pickMenuY = Math.max(4, Math.min(top, Math.max(4, hostH - height - 4)))
    }

    function pickRow(row) {
        var mode = win.pickMode
        var floorText = win.pickFloor || win.openFloor
        var replace = win.pickReplaceIndex
        win.pickMode = ""
        win.pickAnchor = null
        win.pickReplaceIndex = -1
        if (mode === "mon")
            controller.addFloorMonsterFull(floorText, String(row.name || ""),
                                           "1", "")
        else if (mode === "item") {
            if (replace >= 0)
                // 点资源图标换种类：名字/图标/默认效果一起换
                controller.setItemKind(floorText, replace,
                                       String(row.name || ""),
                                       String(row.icon || ""), "")
            else
                controller.addItemFull(floorText, String(row.name || ""),
                                       String(row.effect || ""), "1",
                                       String(row.icon || ""))
        }
    }

    function deleteFloor(floorText) {
        var name = String(floorText || win.openFloor || "")
        if (!win.floorDeleteArm) {
            win.floorDeleteArm = true
            return
        }
        controller.removeFloor(name)
        win.closeFloorSheet(name)
    }

    // ---- 怪物编辑界面 ----
    function draftOf(m) {
        return { name: String(m.name || ""), hp: String(m.hp || ""),
                 atk: String(m.atk || ""), def: String(m.def || ""),
                 gold: String(m.gold || ""), exp: String(m.exp || "") }
    }

    function openMonster(index) {
        var db = (controller ? controller.monsters : null) || []
        if (index < 0 || index >= db.length)
            return
        var m = db[index] || {}
        win.monDraft = win.draftOf(m)
        var rows = []
        var items = m.skill_items || []
        for (var i = 0; i < items.length; i++) {
            var item = items[i] || {}
            var name = String(item.name || "")
            var schema = win.skillSchema(name)
            // 自定义技能：介绍是用户自己写的（存下来的那份），手册里的技能才用手册原话
            var custom = !!item.custom
            var effect = custom ? String(item.effect || "")
                                : win.skillEffect(name)
            rows.push({ name: name,
                        value: String(item.value || ""),
                        effect: effect,
                        custom: custom,
                        schema: schema,
                        params: win.defaultParams(schema, item.params) })
        }
        win.monSkills = rows
        win.monIconId = String(m.icon_id || "")
        win.monIconUrl = String(m.icon || "")
        win.iconPicker = false
        win.skillPicker = false
        win.monEdit = index
        Qt.callLater(monEditor.fill)
    }

    function closeMonster() {
        win.monEdit = -1
        win.iconPicker = false
        win.skillPicker = false
        win.monSkills = []
        win.monDraft = ({})
    }

    function setDraft(key, text) {
        var next = {}
        for (var k in win.monDraft)
            next[k] = win.monDraft[k]
        next[key] = String(text)
        win.monDraft = next
    }

    function draftValue(key) {
        var value = win.monDraft ? win.monDraft[key] : ""
        return value === undefined || value === null ? "" : String(value)
    }

    // ---- 技能参数：要填哪几个数由引擎的 skill_params 定（见 skillinfo.params_for） ----
    function skillSchema(name) {
        if (!controller || !name)
            return []
        var list = controller.skillParams(String(name)) || []
        var out = []
        for (var i = 0; i < list.length; i++) {
            var item = list[i] || {}
            out.push({ field: String(item.field || ""),
                       label: String(item.label || ""),
                       unit: String(item.unit || ""),
                       type: String(item.type || "int") })
        }
        return out
    }

    // 参数默认值：数字留空，开关关，"十字/九宫格"默认十字（引擎里 zoneSquare 假就是十字）
    function defaultParams(schema, saved) {
        var out = {}
        var have = saved || {}
        for (var i = 0; i < schema.length; i++) {
            var item = schema[i]
            var value = have[item.field]
            if (value === undefined || value === null)
                value = item.type === "toggle" ? false
                      : item.type === "choice" ? "十字" : ""
            out[item.field] = value
        }
        return out
    }

    function setSkill(index, key, text) {
        var rows = win.monSkills
        if (!rows || index < 0 || index >= rows.length)
            return
        var row = rows[index]
        if (!row)
            return
        // 原地改，不换数组：换数组会让 Repeater 重建，正在打字的输入框会丢焦点
        row[key] = String(text)
        if (key === "name" && row.custom) {
            // 自定义那行改成了手册里的技能名：介绍/参数格跟着换（这一步允许重画）
            var known = win.skillEffect(row.name)
            if (known !== "")
                row.effect = known
            var schema = win.skillSchema(row.name)
            row.schema = schema
            row.params = win.defaultParams(schema, row.params)
            win.monSkills = rows.slice(0)
        }
    }

    function setSkillParam(index, field, value) {
        var rows = win.monSkills
        if (!rows || index < 0 || index >= rows.length)
            return
        var row = rows[index]
        if (!row || !row.params)
            return
        row.params[field] = value
    }

    // 开关/二选一改完要重画（数字框不用：它自己就是输入中的那份文字）
    function setSkillFlag(index, field, value) {
        win.setSkillParam(index, field, value)
        win.monSkills = win.monSkills.slice(0)
    }

    function skillRow(name) {
        var token = String(name || "")
        var schema = win.skillSchema(token)
        return { name: token, value: "",
                 effect: win.skillEffect(token),
                 custom: token === "",
                 schema: schema,
                 params: win.defaultParams(schema, {}) }
    }

    function addSkill(name) {
        var rows = []
        for (var i = 0; i < win.monSkills.length; i++) {
            var row = win.monSkills[i] || {}
            rows.push({ name: String(row.name || ""),
                        value: String(row.value || ""),
                        effect: String(row.effect || ""),
                        custom: !!row.custom,
                        schema: row.schema || [],
                        params: row.params || {} })
        }
        rows.push(win.skillRow(name))
        win.monSkills = rows
    }

    function removeSkill(index) {
        var rows = []
        for (var i = 0; i < win.monSkills.length; i++) {
            if (i === index)
                continue
            var row = win.monSkills[i] || {}
            rows.push({ name: String(row.name || ""),
                        value: String(row.value || ""),
                        effect: String(row.effect || ""),
                        custom: !!row.custom,
                        schema: row.schema || [],
                        params: row.params || {} })
        }
        win.monSkills = rows
    }

    function skillEffect(name) {
        if (!controller || !name)
            return ""
        return String(controller.skillEffect(String(name)) || "")
    }

    function skillNames() {
        var list = (controller ? controller.skillCatalog : null) || []
        var out = []
        for (var i = 0; i < list.length; i++) {
            var name = String(list[i] || "")
            if (name !== "")
                out.push(name)
        }
        return out
    }

    // ---- 技能下拉菜单：一个按钮，菜单里是"自定义 + 手册里的技能" ----
    function openSkillMenu() {
        win.skillPicker = true
        Qt.callLater(win.placeSkillMenu)   // 等按钮排好版再量位置
    }

    function placeSkillMenu() {
        if (!win.skillPicker)
            return
        // 摆哪儿由下拉自己算（它知道自己多大）：这里只把「加技能」按钮的矩形递过去
        skillPicker.placeUnder(monEditor.skillAnchorBox())
    }


    // 素材库按"类"分组：`[{kind, items}]`，搜索时组和格子一起过滤
    // （用户："要有种族的标题"）
    function iconGroups() {
        var groups = (controller ? controller.monsterIconGroups() : null) || []
        var query = win.iconQuery.trim().toLowerCase()
        var out = []
        for (var i = 0; i < groups.length; i++) {
            var group = groups[i] || {}
            var rows = group.items || []
            var kept = []
            for (var j = 0; j < rows.length; j++) {
                if (query === "" || win.iconMatches(rows[j] || {}, query))
                    kept.push(rows[j])
            }
            if (kept.length > 0)
                out.push({ "kind": group.kind, "items": kept })
        }
        return out
    }

    // 搜索按名字/编号过滤（用户："素材库改成图片加名称且需要支持搜索"）；
    // 两座塔各存一份的图并成一张后，另一条的名字在 aliases 里，也搜得到。
    function iconChoices() {
        var groups = win.iconGroups()
        var out = []
        for (var i = 0; i < groups.length; i++) {
            var rows = groups[i].items || []
            for (var j = 0; j < rows.length; j++)
                out.push(rows[j])
        }
        return out
    }

    function iconMatches(row, query) {
        if (String(row.name || "").toLowerCase().indexOf(query) >= 0)
            return true
        if (String(row.id || "").toLowerCase().indexOf(query) >= 0)
            return true
        var aliases = row.aliases || []
        for (var i = 0; i < aliases.length; i++) {
            if (String(aliases[i] || "").toLowerCase().indexOf(query) >= 0)
                return true
        }
        return false
    }

    // 角标：没搜索时"N 张"，搜索时"N / 总数 张"
    function iconCountText() {
        var shown = win.iconChoices().length
        if (win.iconQuery.trim() === "")
            return shown + " 张"
        var total = ((controller ? controller.monsterIconChoices() : null)
                     || []).length
        return shown + " / " + total + " 张"
    }

    function openIconPicker() {
        // 搜索框是"输入框 → iconQuery"单向的：打开时把两边都清掉，
        // 不然上次搜的词还留在框里、素材却全列出来了（框由素材库自己清）
        win.iconQuery = ""
        win.iconSearchMode = false
        win.iconPicker = true
    }

    // 用户拍板：面板开着的时候窗口缩放 → 直接关掉（不跟着重算位置）
    function closeIconPickerIfOpen() {
        if (win.iconPicker)
            win.iconPicker = false
    }

    // 头像库面板的位置：贴在**头像上方**（用户："像qq的表情包显示在上方"）。
    // 上方不够就翻到下方；两边都紧时用空间大的那边，高度按那边的空间缩 ——
    // 无论哪种都只占一小块：不铺满、不压暗、不居中。
    function placeIconPicker() {
        if (!win.iconPicker)
            return
        var w = Math.min(280, win.width - 16)
        var height = Math.min(330, win.height - 16)
        var x = (win.width - w) / 2
        var y = (win.height - height) / 2
        // 头像在修改卡片抬头里；卡片没开（预览/测试直接置位）才摆窗口中间
        if (win.monEdit >= 0) {
            var box = monEditor.iconAnchorBox()
            var at = box
            var boxH = box.height
            // 面板和窗口边各留 8，所以能用的空间要扣掉两头
            var above = at.y - 16
            var below = win.height - (at.y + boxH + 16)
            // 上方放得下够用的高度就放上方（用户要的位置），否则翻到下方
            var useAbove = above >= 200 || above >= below
            height = Math.max(120, Math.min(330, useAbove ? above : below))
            y = useAbove ? at.y - 8 - height : at.y + boxH + 8
            x = at.x + box.width / 2 - w / 2
        }
        win.iconMenuW = w
        win.iconMenuH = height
        win.iconMenuX = Math.max(8, Math.min(win.width - 8 - w, x))
        win.iconMenuY = Math.max(8, Math.min(win.height - 8 - height, y))
    }

    function iconUrlOf(entryId) {
        if (!entryId || !controller)
            return ""
        return String(controller.libraryUrl(entryId) || "")
    }

    function pickIcon(entryId) {
        win.monIconId = String(entryId || "")
        win.monIconUrl = win.iconUrlOf(win.monIconId)
        win.iconPicker = false
    }

    function saveMonster() {
        if (win.monEdit < 0)
            return
        // 手册里的技能只送 name / value / params：effect（介绍）和 code 由 Python 侧
        // 查表补；自定义技能手册里没有介绍，只能把用户写的那句话一起存下来。
        var payload = []
        for (var i = 0; i < win.monSkills.length; i++) {
            var row = win.monSkills[i] || {}
            var entry = { name: String(row.name || ""),
                          value: String(row.value || ""),
                          params: row.params || {} }
            if (row.custom) {
                entry.custom = true
                entry.effect = String(row.effect || "")
            }
            payload.push(entry)
        }
        controller.saveMonsterFull(win.monEdit, win.draftValue("name"),
                                   win.draftValue("hp"), win.draftValue("atk"),
                                   win.draftValue("def"), win.draftValue("exp"),
                                   JSON.stringify(payload), win.monIconId, "",
                                   win.draftValue("gold"))
        win.closeMonster()
    }

    function deleteMonster() {
        if (win.monEdit < 0)
            return
        // 和列表行尾的 ✕ 一样：手册记录 + 各层地图里的记录一起删，
        // 不然"删除这只"之后那一行还留在地图上（看着像没删掉）
        var db = (controller ? controller.monsters : null) || []
        var name = win.monEdit < db.length
                   ? String((db[win.monEdit] || {}).name || "") : ""
        if (name !== "")
            controller.removeMonsterByName(name)
        else
            controller.removeMonster(win.monEdit)
        win.closeMonster()
    }

    // 关子界面：Esc 和"点遮罩"都走这里（顺序：大图 > 怪物编辑 > 挑选层 > 地图子界面）
    function closeTopLayer() {
        if (win.iconPicker) {
            win.iconPicker = false
            return true
        }
        if (win.skillPicker) {
            win.skillPicker = false
            return true
        }
        if (win.monEdit >= 0) {
            win.closeMonster()
            return true
        }
        if (win.pickMode !== "") {
            win.pickMode = ""
            return true
        }
        if (win.floorWindows.length > 0) {
            win.closeTopFloorWindow()
            return true
        }
        return false
    }

    function toggleCollapsed() {
        win.collapsed = !win.collapsed
    }

    Shortcut {
        sequence: "Esc"
        // 正在打字时 Esc 只收键盘（别把人踢出程序）
        enabled: !chatLog.inputFocused
        onActivated: {
            // 先关最上面那层子界面（大图 / 怪物编辑 / 挑选层 / 这一层）
            if (win.closeTopLayer())
                return
            if (win.collapsed) {
                win.toggleCollapsed()
            } else {
                controller.quit()
            }
        }
    }

    onCollapsedChanged: {
        if (!controller)
            return
        // 动画期间改的是"形状"，不是用户拉的尺寸：别记进 userHeight
        win.animatingSize = true
        if (collapsed)
            controller.animateSize(win.userWidth > 0 ? win.userWidth : collapsedWidth,
                                   collapsedHeight, 180)
        else
            controller.animateSize(win.userWidth > 0 ? win.userWidth : expandedWidth,
                                   win.userHeight > 0 ? win.userHeight : expandedHeight,
                                   180)
    }

    Connections {
        target: controller
        function onMapHistoryChanged() { win.sync() }
        function onMonstersChanged() { win.sync() }
        function onSkillStatsChanged() { win.sync() }
        function onChatLogChanged() { win.sync() }
        function onChattingChanged() { win.sync() }
        function onStatusTextChanged() { win.sync() }
        function onChatReplyChanged() { win.sync() }
        function onSessionHintChanged() { win.sync() }
        function onReadingChanged() {
            if (!controller.reading)
                win.readingMode = ""
            win.sync()
        }
        function onTasksChanged() { win.refreshFlash() }
        function onSizeAnimDone() {
            win.animatingSize = false
            // 动画停在用户尺寸（或内容高度）上：把它当成我们自己设的
            win.autoHeight = win.height
            win.refreshExpanded()
        }
    }

    Component.onCompleted: {
        win.sync()
        Qt.callLater(win.refreshExpanded)
        Qt.callLater(win.bindBackSize)
    }

    // ---- 子界面里用的小按钮（幽灵 / 实心两档） ----

    // ---- 面板 ----
    Rectangle {
        id: card
        anchors.fill: parent
        radius: 10
        color: win.paper
        border.width: 1
        border.color: win.edge
        clip: true

        // 入场：淡入 + 从 0.992 放大（属性默认是终态，动画没跑也不会把面板弄没）
        opacity: 1
        scale: 1
        ParallelAnimation {
            id: entrance
            running: false
            NumberAnimation {
                target: card
                property: "opacity"
                from: 0
                to: 1
                duration: 200
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: card
                property: "scale"
                from: 0.992
                to: 1
                duration: 200
                easing.type: Easing.OutCubic
            }
        }

        Connections {
            target: win
            function onEnteredChanged() {
                if (!win.entered)
                    return
                // startup 会先把上次的位置/尺寸写进来（那是命令式赋值，绑定已断），
                // 窗口真显示之后再把"高度跟内容走"的绑定接回去。
                win.bindBackSize()
                entrance.restart()
            }
        }

        // 读到新数据：顶边一条 2px 光带闪一下（不整块变色，文字对比度不掉）
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 1
            anchors.rightMargin: 1
            height: 2
            color: win.barFlash === "err" ? win.danger
                 : (win.barFlash === "ok" ? win.amber : "transparent")
            Behavior on color { ColorAnimation { duration: 120 } }
        }

        // ============ 导航条 / 抬头 / 状态行 ============
        // 代码在 views/main_panel/MainPanel.qml。
        MainPanel { id: panel; host: win }

        // ============ 中间：地图 / 怪物 / 技能（内容长了在这里滚） ============
        Flickable {
            id: flick
            objectName: "contentFlick"
            x: win.padH
            y: panel.chromeBottom + win.gapA
            width: win.bodyW
            // 内容区高度：内容多少、封顶、以及"窗口被拉矮了"三者取最小 ——
            // 用户把窗口拉矮时不该把列表裁掉，而是让它在里面滚
            height: Math.max(60, Math.min(contentHeight, win.middleCap(),
                                          win.height - win.chromeH))
            visible: !win.collapsed
            contentWidth: width
            contentHeight: body.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            // 正在拖怪物行排序时别让这个列表跟着滚（不然一拖就变成滚动）
            interactive: !win.monDragging
            // 行数变了 → 窗口高度跟着变。绑在 contentHeight 上而不是只绑 Column 的
            // implicitHeight：后者要等一次布局，实测加载时拿到的是空态的旧高度
            // （窗口停在 330，内容其实是 490）。
            onContentHeightChanged: win.applyAutoSize()

            MainColumns { id: body; host: win }
        }

        // 内容比窗口高时，右边给一条很细的位置提示
        Rectangle {
            visible: !win.collapsed && flick.contentHeight > flick.height + 1
            width: 2
            radius: 1
            color: win.amber
            opacity: 0.32
            x: card.width - 5
            y: flick.y + flick.visibleArea.yPosition * flick.height
            height: Math.max(18, flick.visibleArea.heightRatio * flick.height)
        }

        // ============ 底部：对话 ============
        ChatDock { id: chatLog; host: win }

        // ============ 地图的小窗：这一层有什么（可多开、可拖、可拉） ============
        // 一扇**真窗口**，每层开一个。
        Component {
            id: floorSheetWindow
            FloorSheetWindow { host: win }
        }

        // ============ 怪物编辑界面（居中卡片） ============
        MonsterEditor { id: monEditor; host: win }

        // ============ 素材库选图 ============
        IconPicker { host: win }

        // ============ 技能挑选（加技能的下拉菜单） ============
        SkillPicker { id: skillPicker; host: win }

        // ============ 伤害计算 ============
        // 另开的一扇窗口。
        Component {
            id: battleWindowComp
            BattleWindow { host: win }
        }

        // ============ 路线对比 ============
        // 几条算好的路线摆一起，比每只怪的掉血。另开的一扇窗口。
        Component {
            id: compareWindowComp
            CompareWindow { host: win }
        }

        // ============ 路线链（docs/ROUTE.md）============
        // 地图上松手生成的那条"交互路线"：勇者 → 格1,1 → 格1,2 …，
        // 点格子填这一格有什么，链尾「计算」沿链算掉血。另开的一扇窗口。
        Component {
            id: routeWindowComp
            RouteWindow { host: win }
        }
    }
}
