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
    // 抬头 / 状态行都可能不占高（没读到东西时折叠态只剩导航条一条）
    height: host.navH + host.headerBlock + host.statusBlock

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
        Item {
            id: refreshBtn
            objectName: "statusRefresh"
            anchors.left: heroMark.visible ? heroMark.right : parent.left
            anchors.leftMargin: heroMark.visible ? 6 : 0
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            Text {
                anchors.centerIn: parent
                text: controller && controller.updating ? "…" : "↻"
                color: refreshMouse.containsMouse ? host.amber
                     : (controller && controller.updating ? host.ink3 : host.ink2)
                font.pixelSize: 12
            }
            MouseArea {
                id: refreshMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.updateStatus()
            }
        }

        // 伤害计算：一扇自己的窗口（可以摆在游戏旁边边打边算）。
        // 放在导航条上是刻意的：它是"工具"，不属于任何一栏数据，
        // 而且收起状态也点得到。
        Item {
            id: battleBtn
            objectName: "battleOpen"
            anchors.right: closeBtn.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            Text {
                anchors.centerIn: parent
                text: "⚔"
                color: battleMouse.containsMouse ? host.amber : host.ink2
                font.pixelSize: 11
            }
            MouseArea {
                id: battleMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: host.openBattle()
            }
        }

        // 关闭：11px 的小叉，悬停才染红
        Item {
            id: closeBtn
            objectName: "closeBtn"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            Text {
                anchors.centerIn: parent
                text: "✕"
                color: closeMouse.containsMouse ? host.danger : host.ink3
                font.pixelSize: 11
            }
            MouseArea {
                id: closeMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.quit()
            }
        }
    }

    // ---------------- 抬头：塔名 ----------------
    // 没读到塔时整行不占位（不留一条空白）。刷新 ↻ 在导航条上，
    // 所以这行只有塔名，没有按钮。
    Item {
        id: header
        objectName: "header"
        y: host.navH + host.navGap
        width: parent.width
        height: host.headerVisible ? host.headerH : 0
        visible: host.headerVisible

        Text {
            id: towerLabel
            objectName: "towerLabel"
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 1
            width: parent.width
            text: host.tower
            color: host.ink
            font.family: host.uiFont
            font.pixelSize: 16
            font.bold: true
            elide: Text.ElideRight
        }
    }

    // ---------------- 状态：血/攻/防/魔防 一行，金币 + 四色钥匙 一行 ----------------
    // 用户："顶部状态行改成血攻防魔防一行，钥匙一行"。
    // 两行都跟下面"地图/怪物/技能"的左边线对齐；收起时也留着（瞄一眼用）。
    Item {
        id: statusRow
        objectName: "statusRow"
        y: host.navH + host.headerBlock
        width: parent.width
        height: host.statusBlock
        visible: host.statusVisible

        // 人物状态锁：锁住后「读取」不再改状态面板（用户要求）
        Rectangle {
            objectName: "statusLock"
            anchors.right: parent.right
            anchors.top: parent.top
            width: 24
            height: 16
            radius: 4
            color: controller && controller.statusLocked
                   ? Qt.rgba(0.84, 0.62, 0.18, 0.20) : "transparent"
            border.width: 1
            border.color: host.hairline
            Text {
                anchors.centerIn: parent
                text: "锁"
                color: controller && controller.statusLocked
                       ? host.amber : host.ink3
                font.family: host.uiFont
                font.pixelSize: 9
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: if (controller) controller.toggleStatusLock()
            }
        }

        Column {
            anchors.left: parent.left
            anchors.top: parent.top
            spacing: 2

            // 第一行：生命 / 攻击 / 防御 / 魔防
            Row {
                id: stats
                objectName: "statChips"
                spacing: 9

                Repeater {
                    model: [
                        ["hp", host.statusValue("hp")],
                        ["atk", host.statusValue("atk")],
                        ["def", host.statusValue("def")],
                        ["mdef", host.statusValue("mdef")]
                    ]
                    delegate: Row {
                        spacing: 2
                        visible: modelData[1] !== ""
                        Image {
                            width: 11
                            height: 11
                            anchors.verticalCenter: parent.verticalCenter
                            source: host.iconBase && modelData[0] !== ""
                                    ? host.iconBase + modelData[0] + ".png" : ""
                            smooth: false
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData[1]
                            color: host.ink
                            font.family: host.monoFont
                            font.pixelSize: 10
                        }
                    }
                }
            }

            // 第二行：金币 + 四色钥匙（都是"身上有多少"）
            Row {
                id: resRow
                objectName: "resChips"
                spacing: 8

                Row {
                    objectName: "goldChip"
                    spacing: 2
                    visible: host.statusValue("gold") !== ""
                    Image {
                        width: 11
                        height: 11
                        anchors.verticalCenter: parent.verticalCenter
                        source: host.iconBase ? host.iconBase + "gold.png" : ""
                        smooth: false
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: host.statusValue("gold")
                        color: host.ink
                        font.family: host.monoFont
                        font.pixelSize: 10
                    }
                }

                Row {
                    id: keyRow
                    objectName: "keyChips"
                    spacing: 8

                    Repeater {
                        model: [
                            ["key_yellow", host.keyValue("yellow")],
                            ["key_blue", host.keyValue("blue")],
                            ["key_red", host.keyValue("red")],
                            ["key_green", host.keyValue("green")]
                        ]
                        delegate: Row {
                            spacing: 2
                            visible: modelData[1] !== ""
                            Image {
                                width: 10
                                height: 10
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
                                font.pixelSize: 9
                            }
                        }
                    }
                }
            }
        }
    }
}
