import QtQuick
import QtQuick.Controls.Basic
// 共用件（配色/按钮）在上一层
import "../shared"

// 卡片顶部这一块：导航条（刷新状态 / ⚔ 伤害计算 / 关）+ 抬头（塔名）+ 状态行
// （生命/攻击/防御/魔防 + 四色钥匙）。软件名已经删掉，换成刷新按钮（用户要求）。
//
// 主窗口的一块（不是覆盖层），一个界面一个文件夹。
// 它只画和拖；数值来自 host（`host.tower`、`host.statusValue(...)`、
// `host.floorList`…），折叠状态也是 host 的（`host.collapsed` / `host.headerBlock`）。
// 外面只用到一个数：`chromeBottom`（滚动区从这儿开始）。
Item {
    id: chrome

    // 归属：主窗口（塔名/数值/折叠状态都在它身上）
    property var host

    // 自己底部在父坐标里的 y：下面那块滚动区（flick）从这儿开始
    readonly property real chromeBottom: chrome.y + chrome.height
    x: host.padH
    y: host.padV
    width: host.bodyW
    // 状态卡可能不占高（没读到东西时折叠态只剩导航条一条）
    height: host.navH + host.heroBlock

    // 拖动 / 点一下收起。声明在按钮之前：后声明的兄弟在上层，按钮才点得到。
    MouseArea {
        id: dragArea
        objectName: "dragArea"
        anchors.fill: parent
        hoverEnabled: true
        // 平时就是普通箭头：整条抬头是"铬件"，不是按钮，鼠标一进来就变手很蠢。
        // 只有真按住往外拖的时候才换成"抓着手"，那才是拖动该有的反馈。
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.ArrowCursor

        property real pressX: 0
        property real pressY: 0
        property bool moved: false
        property bool engaged: false

        onPressed: function (m) {
            engaged = true
            pressX = m.x
            pressY = m.y
            moved = false
        }
        onPositionChanged: function (m) {
            if (!pressed)
                return
            if (!moved) {
                if (Math.abs(m.x - pressX) <= 3 && Math.abs(m.y - pressY) <= 3)
                    return
                moved = true
                controller.dragStart(pressX, pressY)
            }
        }
        onReleased: {
            if (!engaged)
                return
            engaged = false
            if (moved)
                controller.dragEnd()
            else
                host.toggleCollapsed()
        }
    }

    // ---------------- 导航条 ----------------
    Item {
        id: navBar
        objectName: "topBar"
        width: parent.width
        height: host.navH

        Image {
            id: heroMark
            objectName: "heroIcon"
            x: 0
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            source: host.heroIcon
            visible: host.heroIcon !== ""
            fillMode: Image.PreserveAspectFit
            smooth: false
        }

        // 刷新状态（只刷人物面板、不读图）：原来在导航条右边，挪到软件名这里
        // （用户："显示标题的地方删掉，换成刷新按钮"）。
        IconBtn {
            id: refreshBtn
            objectName: "statusRefresh"
            anchors.left: heroMark.visible ? heroMark.right : parent.left
            anchors.leftMargin: heroMark.visible ? 4 : 0
            anchors.verticalCenter: parent.verticalCenter
            glyph: controller && controller.updating ? "…" : "↻"
            dim: controller && controller.updating
            onClicked: controller.updateStatus()
        }

        // 置顶：默认关。开了窗口（连同所有子窗口）永远在别的应用上面；关了就和普通
        // 窗口一样，切到别的应用会被盖住，点任务栏图标 / Alt+Tab 叫回来。
        TextBtn {
            id: pinBtn
            objectName: "pinToggle"
            anchors.right: gainBtn.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            pill: true
            text: "置顶"
            accent: Theme.amber
            active: host.pinned
            onClicked: controller.setPinned(!host.pinned)
        }

        // 加属性收益：自己的工具，和伤害计算并列（用户："这是新功能！！！不要和
        // 之前的混在一起！！！"），所以给它自己的入口，放在 ⚔ 左边。
        IconBtn {
            id: gainBtn
            objectName: "gainOpen"
            anchors.right: battleBtn.left
            anchors.rightMargin: 2
            anchors.verticalCenter: parent.verticalCenter
            glyph: "＋"
            onClicked: host.openGain()
        }

        // 伤害计算：一扇自己的窗口（可以摆在游戏旁边边打边算）。
        // 放在导航条上是刻意的：它是"工具"，不属于任何一栏数据，
        // 而且收起状态也点得到。
        IconBtn {
            id: battleBtn
            objectName: "battleOpen"
            anchors.right: compareBtn.left
            anchors.rightMargin: 2
            anchors.verticalCenter: parent.verticalCenter
            glyph: "⚔"
            onClicked: host.openBattle()
        }

        // 路线对比：在伤害计算右边（用户："入口就在伤害计算的右边"）。
        // 把算好的路线粘贴/拖进来，比每只怪掉多少血。
        IconBtn {
            id: compareBtn
            objectName: "compareOpen"
            anchors.right: closeBtn.left
            anchors.rightMargin: 2
            anchors.verticalCenter: parent.verticalCenter
            glyph: "⇄"
            onClicked: host.openCompare()
        }

        // 关闭：悬停才染红
        IconBtn {
            id: closeBtn
            objectName: "closeBtn"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            glyph: "✕"
            hoverInk: Theme.danger
            hoverBack: Theme.dangerSoft
            onClicked: controller.quit()
        }
    }

    // ---------------- 状态卡：塔名 + 四个小块 + 金币钥匙胶囊 ----------------
    // 没读到塔、也没数值时整张卡不占位。刷新 ↻ 在导航条上，卡里没有按钮。
    // 卡高 = host.heroH（主窗口按这两块的高度算窗口高度）。
    Card {
        id: hero
        objectName: "hero"
        y: host.navH + host.navGap
        width: parent.width
        visible: host.heroVisible
        pad: host.heroPad

        Item {
            id: header
            objectName: "header"
            width: parent.width
            height: host.headerVisible ? host.headerH + 6 : 0
            visible: host.headerVisible

            Text {
                id: towerLabel
                objectName: "towerLabel"
                anchors.left: parent.left
                anchors.top: parent.top
                // 右边留给「锁」
                width: parent.width - 40
                height: host.headerH
                verticalAlignment: Text.AlignVCenter
                text: host.tower
                color: host.ink
                font.family: host.uiFont
                font.pixelSize: 17
                font.bold: true
                elide: Text.ElideRight
            }
        }

        // 四个小块 + 一行胶囊
        Item {
            id: statusRow
            objectName: "statusRow"
            width: parent.width
            height: host.statusH
            visible: host.statusVisible

            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 8

                // 第一行：生命 / 攻击 / 防御 / 魔防，四个等宽的小块
                // （格子位置固定：哪个没读到就空着，不让后面的往前挤）
                Row {
                    id: stats
                    objectName: "statChips"
                    width: parent.width
                    spacing: 6

                    Repeater {
                        model: [
                            ["hp", "生命", host.statusValue("hp")],
                            ["atk", "攻击", host.statusValue("atk")],
                            ["def", "防御", host.statusValue("def")],
                            ["mdef", "魔防", host.statusValue("mdef")]
                        ]
                        delegate: Rectangle {
                            width: (stats.width - 3 * stats.spacing) / 4
                            height: 46
                            radius: 6
                            color: Theme.tile
                            visible: true
                            Row {
                                x: 8
                                y: 7
                                spacing: 4
                                Image {
                                    width: 12
                                    height: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    source: host.iconBase
                                            ? host.iconBase + modelData[0] + ".png" : ""
                                    smooth: false
                                }
                                Text {
                                    text: modelData[1]
                                    color: host.ink3
                                    font.family: host.uiFont
                                    font.pixelSize: 10
                                }
                            }
                            Text {
                                x: 8
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 6
                                width: parent.width - 12
                                text: modelData[2] !== "" ? modelData[2] : "—"
                                color: modelData[2] !== "" ? host.ink : host.ink3
                                font.family: host.monoFont
                                font.pixelSize: 16
                                font.bold: true
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                // 第二行：金币 + 四色钥匙（都是"身上有多少"），每样一颗胶囊
                Row {
                    id: resRow
                    objectName: "resChips"
                    spacing: 6

                    Rectangle {
                        objectName: "goldChip"
                        visible: host.statusValue("gold") !== ""
                        width: goldRow.width + 16
                        height: 24
                        radius: 12
                        color: Theme.chip
                        Row {
                            id: goldRow
                            anchors.centerIn: parent
                            spacing: 4
                            Image {
                                width: 12
                                height: 12
                                anchors.verticalCenter: parent.verticalCenter
                                source: host.iconBase ? host.iconBase + "gold.png" : ""
                                smooth: false
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: host.statusValue("gold")
                                color: host.ink
                                font.family: host.monoFont
                                font.pixelSize: 12
                                font.bold: true
                            }
                        }
                    }

                    Row {
                        id: keyRow
                        objectName: "keyChips"
                        spacing: 6

                        Repeater {
                            model: [
                                ["key_yellow", host.keyValue("yellow")],
                                ["key_blue", host.keyValue("blue")],
                                ["key_red", host.keyValue("red")],
                                ["key_green", host.keyValue("green")]
                            ]
                            delegate: Rectangle {
                                visible: modelData[1] !== ""
                                width: keyInner.width + 16
                                height: 24
                                radius: 12
                                color: Theme.chip
                                Row {
                                    id: keyInner
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Image {
                                        width: 12
                                        height: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        source: host.iconBase && modelData[0] !== ""
                                                ? host.iconBase + modelData[0] + ".png" : ""
                                        smooth: false
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData[1]
                                        color: host.ink2
                                        font.family: host.monoFont
                                        font.pixelSize: 12
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // 人物状态锁：锁住后「读取」不再改状态面板（用户要求）。
    // 摆在状态卡的右上角（卡里是自上而下排的，这个单独浮在上面）。
    Rectangle {
        objectName: "statusLock"
        visible: host.heroVisible
        x: hero.x + hero.width - host.heroPad - width
        y: hero.y + host.heroPad + 2
        z: 2
        width: 32
        height: 22
        radius: Theme.radius
        color: controller && controller.statusLocked
               ? Theme.amberSoft
               : (lockMouse.containsMouse ? Theme.hover : "transparent")
        border.width: 1
        border.color: controller && controller.statusLocked
                      ? Theme.amber : Theme.edge
        Text {
            anchors.centerIn: parent
            text: "锁"
            color: controller && controller.statusLocked
                   ? host.amber : host.ink3
            font.family: host.uiFont
            font.pixelSize: 11
        }
        MouseArea {
            id: lockMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: if (controller) controller.toggleStatusLock()
        }
    }
}
