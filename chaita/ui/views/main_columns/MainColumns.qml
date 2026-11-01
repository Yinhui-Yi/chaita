import QtQuick
import QtQuick.Controls.Basic
// 共用件（配色/按钮）在上一层
import "../shared"
// 地图那一栏的卡片（大图在 map_view/MapWindow.qml）
import "../map_view"

// 中间三栏 + 读取记录：地图（只显示选中的那一层）、怪物（手册数值 × 地图数量）、
// 技能（按地图上出现过的怪统计）、读取记录（每点一次读取一条）。
//
// 主窗口的一块（不是覆盖层）。滚动容器是外面那层 `flick`（Flickable），
// 这里只是它里面的 `Column`；所以外层要 `flick.contentHeight: body.implicitHeight`，
// 那边仍用 id `body` 指过来。
//
// 三栏都能各自折叠（host.mapCollapsed / monCollapsed / skillCollapsed），
// 折叠状态和列表数据都在 host 上，这里只画和点。
Column {
    id: body

    // 归属：主窗口（列表数据、折叠状态、拖动状态都在它身上）
    property var host

    // 主窗口要量的两处位置（要量就问这里，别跨文件摸 mapCard / monRep 这些内部 id）
    // 地图卡片在场景里的下沿：「这一层」小窗默认开在它下面，别盖住地图本身
    function mapBottom() {
        return mapCard.mapToItem(null, 0, mapCard.height).y
    }

    // 第一行怪在场景里的上沿（-1 = 还没有行）：拖动排序时要把屏幕坐标对上
    function firstRowTop() {
        var first = monRep.itemAt(0)
        return first ? first.mapToItem(null, 0, 0).y : -1
    }

    objectName: "contentBody"
    width: host.bodyW
    spacing: 0
    // 行数/内容变了，窗口高度跟着走（内容决定高度，不留一截空白）

    // ---------- 上次留下的记录：只提示，点「恢复」才加载 ----------
    // 不自动恢复：旧血量/旧钥匙会误导人；层和怪是手工劳动，值得留一份。
    Item {
        objectName: "sessionBar"
        width: body.width
        height: host.sessionHint === "" ? 0 : 20
        visible: host.sessionHint !== ""

        Text {
            id: sessionText
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 74
            text: "上次的记录：" + host.sessionHint
            color: host.ink3
            font.family: host.uiFont
            font.pixelSize: 9
            elide: Text.ElideRight
        }
        Text {
            id: sessionRestore
            objectName: "sessionRestore"
            anchors.right: sessionDiscard.left
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: "恢复"
            color: restoreMouse.containsMouse ? host.amber : host.ink2
            font.family: host.uiFont
            font.pixelSize: 9
            MouseArea {
                id: restoreMouse
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.restoreSession()
            }
        }
        Text {
            id: sessionDiscard
            objectName: "sessionDiscard"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "忽略"
            color: discardMouse.containsMouse ? host.ink : host.ink3
            font.family: host.uiFont
            font.pixelSize: 9
            MouseArea {
                id: discardMouse
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.discardSession()
            }
        }
    }

    // ---------- 地图 ----------
    Item {
        width: body.width
        height: 18
        // 点标题（含箭头）折叠/展开这一栏
        Item {
            id: mapSectionHead
            objectName: "mapSectionHead"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(60, mapHeadLabel.width + 16)
            height: 18
            Text {
                objectName: "mapChevron"
                x: 0
                anchors.verticalCenter: parent.verticalCenter
                width: 10
                text: host.mapCollapsed ? "▸" : "▾"
                color: mapHeadMouse.containsMouse ? host.amber : host.ink3
                font.pixelSize: 9
            }
            Text {
                id: mapHeadLabel
                objectName: "mapSectionLabel"
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                text: host.mapCollapsed
                      ? "地图  " + host.floorList.length + " 层"
                      : "地图"
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 10
                font.letterSpacing: 2
            }
            MouseArea {
                id: mapHeadMouse
                anchors.fill: parent
                anchors.rightMargin: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: host.toggleMapSection()
            }
        }
        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Text {
                id: readTipText
                objectName: "readTip"
                anchors.verticalCenter: parent.verticalCenter
                text: host.readTip
                color: host.ink3
                font.family: host.monoFont
                font.pixelSize: 9
                elide: Text.ElideRight
                width: Math.min(readTipText.implicitWidth, 86)
                horizontalAlignment: Text.AlignRight
                visible: text !== "" && host.floorList.length > 0
            }
            // 读取（只读地图）：挨着地图条，不在对话框里。
            // 已经在读也能再点（并行读取）。按钮上的字**永远是「读取」**：
            // 手册是分页的，翻到下一页还得再点它；写成「读取中」会让人以为
            // 不能再按（用户："要通过按读取中来开启第二页太反直觉"）。
            // 正在读用右上角一颗呼吸的小点表示，按钮本身照样能点。
            Rectangle {
                id: readMapBtn
                objectName: "readMap"
                anchors.verticalCenter: parent.verticalCenter
                width: 46
                height: 20
                radius: 6
                readonly property int busy: host.runningCount("map")
                color: host.amber
                Text {
                    anchors.centerIn: parent
                    text: "读取"
                    color: host.amberInk
                    font.family: host.uiFont
                    font.pixelSize: 10
                    font.bold: true
                }
                Rectangle {
                    objectName: "mapBusyDot"
                    visible: readMapBtn.busy > 0
                    x: readMapBtn.width - 7
                    y: -2
                    width: 7
                    height: 7
                    radius: 3.5
                    color: host.amberInk
                    border.width: 1
                    border.color: host.amber
                    SequentialAnimation on opacity {
                        running: readMapBtn.busy > 0
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 600 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 600 }
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.readMode("map")
                }
            }
        }
    }

    // 出错时那句话就贴在读取按钮下面（不占位时高度为 0）
    Text {
        objectName: "errorText"
        width: body.width
        height: host.notice === "" ? 0 : 14
        visible: host.notice !== ""
        topPadding: 2
        text: host.notice
        color: host.danger
        font.family: host.uiFont
        font.pixelSize: 9
        elide: Text.ElideRight
    }

    Item { width: body.width; height: 4 }

    // 地图只画**这一层**，但画得大：左边侧栏快速切层、右边大图，
    // 其余层压在大图后面只露一角（用户 2026-10-30）。
    MapPanel {
        id: mapCard
        host: body.host
    }
    Text {
        width: body.width
        height: host.floorList.length === 0 && !host.mapCollapsed ? 34 : 0
        visible: host.floorList.length === 0 && !host.mapCollapsed
        text: "还没有地图。点这栏的「读取」，一层一层记进来。"
        color: host.ink3
        font.family: host.uiFont
        font.pixelSize: 10
        wrapMode: Text.WordWrap
    }

    Item { width: body.width; height: host.gapB }

    // ---------- 怪物 ----------
    Item {
        width: body.width
        height: 18
        Item {
            id: monSectionHead
            objectName: "monSectionHead"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(60, monHeadLabel.width + 16)
            height: 18
            Text {
                objectName: "monChevron"
                x: 0
                anchors.verticalCenter: parent.verticalCenter
                width: 10
                text: host.monCollapsed ? "▸" : "▾"
                color: monHeadMouse.containsMouse ? host.amber : host.ink3
                font.pixelSize: 9
            }
            Text {
                id: monHeadLabel
                objectName: "monSectionLabel"
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                text: "怪物"
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 10
                font.letterSpacing: 2
            }
            MouseArea {
                id: monHeadMouse
                anchors.fill: parent
                anchors.rightMargin: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: host.toggleMonSection()
            }
        }
        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Text {
                objectName: "monAgg"
                anchors.verticalCenter: parent.verticalCenter
                text: host.monAgg
                color: host.amber
                font.family: host.monoFont
                font.pixelSize: 9
            }
            // 读取（只读怪物手册）：和地图那栏的「读取」分开，
            // 也能并行点（两栏各跑各的）。字永远写「读取」：
            // 手册分页，翻到下一页再点它就行（见上面地图那栏的注释）。
            Rectangle {
                id: readMonBtn
                objectName: "readMon"
                anchors.verticalCenter: parent.verticalCenter
                width: 46
                height: 20
                radius: 6
                readonly property int busy: host.runningCount("monsters")
                color: host.amber
                Text {
                    anchors.centerIn: parent
                    text: "读取"
                    color: host.amberInk
                    font.family: host.uiFont
                    font.pixelSize: 10
                    font.bold: true
                }
                Rectangle {
                    objectName: "monBusyDot"
                    visible: readMonBtn.busy > 0
                    x: readMonBtn.width - 7
                    y: -2
                    width: 7
                    height: 7
                    radius: 3.5
                    color: host.amberInk
                    border.width: 1
                    border.color: host.amber
                    SequentialAnimation on opacity {
                        running: readMonBtn.busy > 0
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 600 }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 600 }
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.readMode("monsters")
                }
            }
        }
    }
    Item { width: body.width; height: 4 }

    Repeater {
        id: monRep
        model: host.monRows
        delegate: Item {
            objectName: "monRow"
            width: body.width
            height: 36
            // 怪物那栏折叠起来时整行让位（Column 会跳过不可见的子项）
            visible: !host.monCollapsed
            // 正在被拖的那一行淡一点：看得出"它在跟着手走"
            // （controller 可能已被回收成 null：绑定里要短路，不然报
            // "Cannot read property 'monDragFrom' of null"）
            opacity: modelData && modelData.dbIndex >= 0
                     && controller
                     && controller.monDragFrom === modelData.dbIndex
                     ? 0.45 : 1

            // 拖到这行前面松手 = 插在这儿
            Rectangle {
                objectName: "monDropLine"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 2
                color: host.amber
                visible: modelData && modelData.dbIndex >= 0
                         && controller
                         && controller.monDragFrom >= 0
                         && controller.monDragTo === modelData.dbIndex
                         && controller.monDragFrom !== modelData.dbIndex
            }

            // 整行：轻点打开编辑，按住上下拖 = 调顺序
            // （拖动交给 Python 读光标，见 beginMonDrag 的注释）
            MouseArea {
                objectName: "monOpen"
                anchors.fill: parent
                hoverEnabled: true
                enabled: modelData && modelData.dbIndex >= 0
                cursorShape: !enabled ? Qt.ArrowCursor
                            : (controller
                               && controller.monDragFrom === modelData.dbIndex
                               ? Qt.ClosedHandCursor
                               : Qt.PointingHandCursor)

                property real pressY: 0
                property bool dragging: false

                onPressed: function (mouse) {
                    pressY = mouse.y
                    dragging = false
                }

                onPositionChanged: function (mouse) {
                    if (!pressed)
                        return
                    // 先走 6px 才算拖：不然手抖一下就把"点行开编辑"
                    // 变成排序
                    if (!dragging) {
                        if (Math.abs(mouse.y - pressY) < 6)
                            return
                        dragging = true
                        host.beginMonDrag(modelData.dbIndex,
                                         parent.height)
                    }
                }

                onReleased: {
                    if (dragging) {
                        dragging = false
                        host.endMonDrag()
                        return
                    }
                    host.openMonster(modelData.dbIndex)
                }

                onCanceled: {
                    // 指针离开这一行时 Qt 会取消抓取 —— 对拖动来说
                    // 这正是"还在拖"，收尾交给 Python（它会看鼠标是否松开）
                    if (dragging) {
                        dragging = false
                        host.endMonDrag()
                    }
                }
            }

            Image {
                id: sprite
                objectName: "monIcon"
                x: 0
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                height: 24
                // 手册抠的那张最准；没有（或那张临时图被清了）就用素材库按名字找
                source: host.hasUrl(modelData ? modelData.icon : "")
                        ? modelData.icon
                        : host.monsterIconNamed(modelData ? modelData.name : "")
                // 按 status 判：URL 指向的文件没了的时候 hasUrl 仍是真，
                // 以前那样会留一个空白洞（用户："缩略图怎么没有了"）
                visible: status === Image.Ready
                fillMode: Image.PreserveAspectFit
                smooth: false
                asynchronous: true
            }
            Rectangle {
                anchors.fill: sprite
                visible: sprite.status !== Image.Ready
                radius: 5
                color: "#EADFCB"
                Text {
                    anchors.centerIn: parent
                    text: modelData && modelData.name
                          ? modelData.name.charAt(0) : "?"
                    color: host.ink2
                    font.family: host.uiFont
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            Text {
                id: monName
                objectName: "monName"
                anchors.left: parent.left
                anchors.leftMargin: 32
                anchors.top: parent.top
                anchors.topMargin: 4
                text: modelData ? modelData.name : ""
                color: host.ink
                font.family: host.uiFont
                font.pixelSize: 13
                font.bold: true
            }
            Text {
                objectName: "monSkill"
                anchors.left: monName.right
                anchors.leftMargin: 8
                anchors.right: monTotal.left
                anchors.rightMargin: 8
                anchors.baseline: monName.baseline
                text: modelData ? modelData.skill : ""
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 9
                elide: Text.ElideRight
            }
            Text {
                id: monTotal
                objectName: "monTotal"
                anchors.right: parent.right
                anchors.rightMargin: 66
                anchors.top: parent.top
                anchors.topMargin: 5
                // 手册里读过、地图上还没记的怪没有 ×N（数字是 0 也不写）
                visible: modelData && modelData.onMap
                text: modelData ? "×" + modelData.total : ""
                color: host.ink3
                font.family: host.monoFont
                font.pixelSize: 10
            }
            Text {
                objectName: "monLeft"
                anchors.right: parent.right
                anchors.rightMargin: 22
                anchors.top: parent.top
                anchors.topMargin: 4
                visible: modelData && modelData.onMap
                text: modelData ? "剩 " + modelData.left : ""
                color: modelData && modelData.left > 0 ? host.amber : host.ink3
                font.family: host.monoFont
                font.pixelSize: 12
                font.bold: true
            }
            Text {
                objectName: "monStats"
                anchors.left: parent.left
                anchors.leftMargin: 32
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 5
                text: modelData ? modelData.stats : ""
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 9
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: host.hairline
            }

            // 最右边：删掉这只（连各层地图里的记录一起删 —— 只删手册
            // 记录的话，地图上用到它的层还会把这行顶出来，看着像没删掉）
            Item {
                objectName: "monDeleteRow"
                x: parent.width - 16
                y: 8
                width: 16
                height: 20
                visible: !!modelData && String(modelData.name || "") !== ""
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: monDeleteMouse.containsMouse
                           ? host.danger : host.ink3
                    font.pixelSize: 10
                }
                MouseArea {
                    id: monDeleteMouse
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: controller.removeMonsterByName(
                                   modelData.name)
                }
            }
        }
    }
    Text {
        width: body.width
        height: host.monRows.length === 0 && !host.monCollapsed ? 24 : 0
        visible: host.monRows.length === 0 && !host.monCollapsed
        text: "还没读到怪。点这栏的「读取」读怪物手册。"
        color: host.ink3
        font.family: host.uiFont
        font.pixelSize: 10
    }

    Item { width: body.width; height: host.gapB }

    // ---------- 技能 ----------
    Item {
        width: body.width
        height: 18
        // 点标题（含箭头）折叠/展开这一栏 —— 和地图/怪物同一个做法
        Item {
            id: skillSectionHead
            objectName: "skillSectionHead"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(60, skillHeadLabel.width + 16)
            height: 18
            Text {
                objectName: "skillChevron"
                x: 0
                anchors.verticalCenter: parent.verticalCenter
                width: 10
                text: host.skillCollapsed ? "▸" : "▾"
                color: skillHeadMouse.containsMouse
                       ? host.amber : host.ink3
                font.pixelSize: 9
            }
            Text {
                id: skillHeadLabel
                objectName: "skillSectionLabel"
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                // 右边 skillAgg 已经写了"N 种 · 涉及 M 只"，
                // 标题就不再重复一遍（和"怪物"那栏一样，只写栏名）
                text: "技能"
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 10
                font.letterSpacing: 2
            }
            MouseArea {
                id: skillHeadMouse
                anchors.fill: parent
                anchors.rightMargin: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: host.toggleSkillSection()
            }
        }
        Text {
            objectName: "skillAgg"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: host.skillAgg
            color: host.ink3
            font.family: host.monoFont
            font.pixelSize: 9
        }
    }
    Item { width: body.width; height: 4 }

    Repeater {
        model: host.skills
        delegate: Item {
            objectName: "skillRow"
            width: body.width
            height: 28
            // 技能那栏折叠起来时整行让位（Column 会跳过不可见的子项）
            visible: !host.skillCollapsed
            Text {
                objectName: "skillName"
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: modelData ? modelData.name : ""
                color: host.ink
                font.family: host.uiFont
                font.pixelSize: 12
                font.bold: true
            }
            Text {
                objectName: "skillLeft"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: modelData
                      ? modelData.total + " 只 · 剩 " + modelData.left : ""
                color: host.amber
                font.family: host.monoFont
                font.pixelSize: 10
                font.bold: true
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: host.hairline
            }
        }
    }
    Text {
        width: body.width
        height: host.skills.length === 0 && !host.skillCollapsed ? 24 : 0
        visible: host.skills.length === 0 && !host.skillCollapsed
        text: "还没读到技能。"
        color: host.ink3
        font.family: host.uiFont
        font.pixelSize: 10
    }

    Item { width: body.width; height: host.gapB }

    // ---------- 读取记录（任务队列） ----------
    // 每点一次「读取」就是一条任务，可以并行：这里逐条列出来，
    // 跑着的能取消、失败的能重试（以前这一栏被砍掉了，用户要回来）
    Item {
        objectName: "taskSection"
        width: body.width
        height: host.tasksView.length === 0 ? 0 : 18
        visible: host.tasksView.length > 0

        Text {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "读取记录"
            color: host.ink3
            font.family: host.uiFont
            font.pixelSize: 10
            font.letterSpacing: 2
        }
        Text {
            objectName: "taskAgg"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: {
                var running = 0
                for (var i = 0; i < host.tasksView.length; i++) {
                    if (host.tasksView[i].state === "running")
                        running += 1
                }
                return running > 0
                    ? ("读着 " + running + " 条 · 共 "
                       + host.tasksView.length + " 条")
                    : (host.tasksView.length + " 条")
            }
            color: host.ink3
            font.family: host.monoFont
            font.pixelSize: 9
        }
    }

    Repeater {
        model: host.tasksView
        delegate: Item {
            objectName: "taskRow"
            width: body.width
            height: host.tasksView.length === 0 ? 0 : 24

            // 状态点：跑着=琥珀、成功=墨、失败=红、取消=浅灰
            Text {
                objectName: "taskDot"
                x: 0
                anchors.verticalCenter: parent.verticalCenter
                text: "●"
                color: modelData.state === "running" ? host.amber
                     : (modelData.state === "failed" ? host.danger
                     : (modelData.state === "done" ? host.ink2 : host.ink3))
                font.pixelSize: 8
            }
            // 这次读取用的那张截图（点开看大图）；没有截图就空着，不留框
            Rectangle {
                objectName: "taskThumb"
                x: 10
                width: 18
                height: 18
                radius: 4
                anchors.verticalCenter: parent.verticalCenter
                color: host.paperLo
                border.width: 1
                border.color: host.hairline
                clip: true
                visible: host.hasUrl(modelData.url)

                Image {
                    anchors.fill: parent
                    anchors.margins: 1
                    source: modelData.url
                    fillMode: Image.PreserveAspectCrop
                    smooth: false
                    asynchronous: true
                }
                // 点这一小块 = 把这次读的那张图放大看（用户 2026-10-31：
                // "我现在点队列里的缩略图怎么不放大"）
                MouseArea {
                    objectName: "taskThumbClick"
                    anchors.fill: parent
                    anchors.margins: -3
                    cursorShape: Qt.PointingHandCursor
                    onClicked: host.showImagePreview(
                        host.hasUrl(modelData.src) ? modelData.src
                                                   : modelData.url)
                }
            }
            Text {
                objectName: "taskMode"
                x: 32
                width: 20
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.modeLabel
                visible: modelData.modeLabel !== ""
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 8
            }
            Text {
                objectName: "taskText"
                anchors.left: parent.left
                anchors.leftMargin: 56
                anchors.right: taskTail.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.text
                color: modelData.state === "failed" ? host.danger : host.ink2
                font.family: host.uiFont
                font.pixelSize: 9
                elide: Text.ElideRight
            }
            Row {
                id: taskTail
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                Text {
                    objectName: "taskElapsed"
                    visible: modelData.elapsed >= 0
                    text: modelData.elapsed >= 0
                          ? modelData.elapsed + "s" : ""
                    color: host.ink3
                    font.family: host.monoFont
                    font.pixelSize: 8
                }
                Text {
                    objectName: "taskCancel"
                    visible: modelData.canCancel
                    text: "取消"
                    color: taskCancelMouse.containsMouse
                           ? host.danger : host.ink3
                    font.family: host.uiFont
                    font.pixelSize: 9
                    MouseArea {
                        id: taskCancelMouse
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: controller.cancelTask(modelData.id)
                    }
                }
                Text {
                    objectName: "taskRetry"
                    visible: modelData.canRetry
                    text: "重试"
                    color: taskRetryMouse.containsMouse
                           ? host.amber : host.ink2
                    font.family: host.uiFont
                    font.pixelSize: 9
                    MouseArea {
                        id: taskRetryMouse
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: controller.retryTask(modelData.id)
                    }
                }
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: host.hairline
            }
        }
    }

    Item { width: body.width; height: host.tasksView.length > 0 ? host.gapB : 0 }
}
