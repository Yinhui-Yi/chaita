import QtQuick
import "../shared"

// 怪物那一张卡：手册数值 × 地图数量。点一行开编辑，按住上下拖 = 调顺序，
// 行尾 ✕ 删掉这只（连各层地图里的记录一起删）。
//
// 一行 36px：头像 · 名字 ……… 「剩 N」· ✕。列表里只给"还剩几只"，别的（生命攻防、技能、
// 总数）都不在这里显示 —— 点一行进编辑卡看、改。
Card {
    id: section
    objectName: "monSectionCard"

    // 归属：主窗口（列表数据、折叠状态、拖动状态都在它身上）
    property var host

    // 一行多高（主窗口按它换算拖动落点）
    readonly property int rowH: 36

    // 第一行怪在场景里的上沿（-1 = 还没有行）：拖动排序时要把屏幕坐标对上
    function firstRowTop() {
        var first = monRep.itemAt(0)
        return first ? first.mapToItem(null, 0, 0).y : -1
    }

    SectionHead {
        width: parent.width
        key: "mon"
        title: "怪物"
        collapsed: host.monCollapsed
        onToggled: host.toggleMonSection()

        Text {
            objectName: "monAgg"
            anchors.verticalCenter: parent.verticalCenter
            text: host.monAgg
            color: Theme.ink3
            font.family: Theme.monoFont
            font.pixelSize: 10
        }
        // 读取（只读怪物手册）：和地图那张卡的「读取」分开，也能并行点（两边各跑各的）
        ReadBtn {
            objectName: "readMon"
            host: section.host
            mode: "monsters"
            busyName: "monBusyDot"
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Item { width: parent.width; height: 2 }

    Repeater {
        id: monRep
        model: host.monRows
        delegate: Item {
            id: row
            objectName: "monRow"
            width: parent.width
            height: section.rowH
            // 怪物这张卡折叠起来时整行让位（Column 会跳过不可见的子项）
            visible: !host.monCollapsed
            // 正在被拖的那一行淡一点：看得出"它在跟着手走"
            // （controller 可能已被回收成 null：绑定里要短路，不然报
            // "Cannot read property 'monDragFrom' of null"）
            opacity: modelData && modelData.dbIndex >= 0
                     && controller
                     && controller.monDragFrom === modelData.dbIndex
                     ? 0.45 : 1

            // 悬停：整行一层浅灰底（点得开、拖得动的提示）
            Rectangle {
                anchors.fill: parent
                anchors.topMargin: 1
                anchors.bottomMargin: 1
                radius: 6
                color: rowMouse.containsMouse ? Theme.paperLo : "transparent"
            }

            // 拖到这行前面松手 = 插在这儿
            Rectangle {
                objectName: "monDropLine"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 2
                color: Theme.amber
                visible: modelData && modelData.dbIndex >= 0
                         && controller
                         && controller.monDragFrom >= 0
                         && controller.monDragTo === modelData.dbIndex
                         && controller.monDragFrom !== modelData.dbIndex
            }

            // 整行：轻点打开编辑，按住上下拖 = 调顺序
            // （拖动交给 Python 读光标，见 beginMonDrag 的注释）
            MouseArea {
                id: rowMouse
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

            // 头像放进一块小的浅色底里（头像本身 24px，不放大）
            Rectangle {
                id: iconTile
                x: 2
                anchors.verticalCenter: parent.verticalCenter
                width: 28
                height: 28
                radius: 6
                color: Theme.tile

                Image {
                    id: sprite
                    objectName: "monIcon"
                    anchors.centerIn: parent
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
                Text {
                    anchors.centerIn: parent
                    visible: sprite.status !== Image.Ready
                    text: modelData && modelData.name
                          ? modelData.name.charAt(0) : "?"
                    color: Theme.ink2
                    font.family: Theme.uiFont
                    font.pixelSize: 12
                    font.bold: true
                }
            }

            Text {
                id: monName
                objectName: "monName"
                anchors.left: iconTile.right
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                // 名字太长就截断，别把右边的「剩 N」顶出去
                width: Math.min(implicitWidth,
                                Math.max(40, monLeft.x - x - 8))
                text: modelData ? modelData.name : ""
                color: Theme.ink
                font.family: Theme.uiFont
                font.pixelSize: 13
                font.bold: true
                elide: Text.ElideRight
            }

            // 「剩 N」：地图上还有几只（手册里读过、地图上还没记的怪没有这个）
            Chip {
                id: monLeft
                objectName: "monLeft"
                x: row.width - 24 - width
                anchors.verticalCenter: parent.verticalCenter
                height: 22
                visible: !!modelData && modelData.onMap
                tone: modelData && modelData.left > 0 ? "accent" : "muted"
                text: modelData ? "剩 " + modelData.left : ""
                mono: true
                bold: true
                fontSize: 12
            }

            // 最右边：删掉这只（连各层地图里的记录一起删 —— 只删手册
            // 记录的话，地图上用到它的层还会把这行顶出来，看着像没删掉）
            Item {
                objectName: "monDeleteRow"
                x: row.width - 18
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                height: 20
                visible: !!modelData && String(modelData.name || "") !== ""
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: monDeleteMouse.containsMouse
                           ? Theme.danger : Theme.ink3
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

            Rectangle {
                anchors.left: iconTile.right
                anchors.leftMargin: 8
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.hairline
            }
        }
    }
    Text {
        width: parent.width
        height: visible ? 28 : 0
        visible: host.monRows.length === 0 && !host.monCollapsed
        verticalAlignment: Text.AlignVCenter
        text: "还没读到怪。点这栏的「读取」读怪物手册。"
        color: Theme.ink3
        font.family: Theme.uiFont
        font.pixelSize: 11
    }
}
