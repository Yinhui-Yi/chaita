import QtQuick
import QtQuick.Controls.Basic

// 素材库选图：点怪物头像弹出来的小窗（QQ 表情包那样贴在头像上方，
// 不铺满、不压暗）。主窗口的覆盖层（z=70），一个界面一个文件夹。
//
// 这里只管「格子怎么摆、搜索、点中哪一张」；开关和定位留在主窗口
// （`host.iconPicker` / `host.iconQuery` / `host.iconMenuX/Y`），因为
// Esc 关最上面那层、窗口变化时收起它，都是主窗口统一判断。
Item {
    id: iconPickerLayer

    // 归属：主窗口（状态和那几个算法都在它身上）
    property var host
    objectName: "iconPicker"
    anchors.fill: parent
    visible: host.iconPicker
    z: 70

    // 打开时把搜索框清掉：搜索框是"输入框 → host.iconQuery"单向的，
    // 两边一起清，不然上次搜的词还留在框里、素材却全列出来了
    onVisibleChanged: if (visible) iconSearch.text = ""

    // 点面板外面就收起。这一层只是接点击的透明层：面板自己带坐标，不贴边
    MouseArea {
        anchors.fill: parent
        onClicked: host.iconPicker = false
    }

    // 影子（照 QQ：白面板浮起来，边缘有一圈很淡的投影）
    Rectangle {
        x: iconCard.x + 1
        y: iconCard.y + 2
        width: iconCard.width + 2
        height: iconCard.height + 2
        radius: 12
        color: Qt.rgba(0.1, 0.08, 0.04, 0.06)
    }
    Rectangle {
        x: iconCard.x - 2
        y: iconCard.y - 2
        width: iconCard.width + 4
        height: iconCard.height + 4
        radius: 13
        color: Qt.rgba(0.1, 0.08, 0.04, 0.04)
    }

    Rectangle {
        id: iconCard
        objectName: "iconCard"
        // 位置和大小是打开那一刻按头像算好的（placeIconPicker），这里只照抄：
        // 面板贴着头像上方浮起，上方真放不下才翻到下方
        x: host.iconMenuX
        y: host.iconMenuY
        width: host.iconMenuW
        height: host.iconMenuH
        radius: 10
        // QQ 是纯白面板（不是我们页面那种米色纸）
        color: "#FFFFFF"
        border.width: 1
        border.color: host.hairline
        clip: true
        // 底部图标栏（两个状态页签和张数都按它定位）
        readonly property int barH: 34
        // 面板左右留白：分组标题和格子都从这里起
        readonly property int padX: 10
        MouseArea { anchors.fill: parent }

        // 张数和关闭放在底部栏右边（QQ 那块没有抬头，第一行就是分组标题）
        Text {
            objectName: "iconCount"
            x: iconCard.width - iconCard.padX - width - 26
            y: iconCard.height - iconCard.barH + 4
            height: 26
            verticalAlignment: Text.AlignVCenter
            text: host.iconCountText()
            color: host.ink3
            font.family: host.monoFont
            font.pixelSize: 9
        }
        Item {
            objectName: "iconClose"
            x: iconCard.width - iconCard.padX - 18
            y: iconCard.height - iconCard.barH + 7
            width: 18
            height: 18
            Text {
                anchors.centerIn: parent
                text: "✕"
                color: iconCloseMouse.containsMouse ? host.danger : host.ink3
                font.pixelSize: 11
            }
            MouseArea {
                id: iconCloseMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: host.iconPicker = false
            }
        }

        // 底部图标栏（照表情包）：左边两个页签，选中的那个戴一层浅色圆角底
        Item {
            objectName: "iconTabSearch"
            x: iconCard.padX
            y: iconCard.height - iconCard.barH + 4
            width: 48
            height: 26
            Rectangle {
                anchors.fill: parent
                radius: 13
                color: host.iconSearchMode ? host.paperLo : "transparent"
            }
            Text {
                anchors.centerIn: parent
                text: "搜索"
                color: host.iconSearchMode ? host.ink : host.ink3
                font.family: host.uiFont
                font.pixelSize: 10
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: { host.iconSearchMode = true
                             iconSearch.forceActiveFocus() }
            }
        }
        Item {
            objectName: "iconTabEmoji"
            x: iconCard.padX + 52
            y: iconCard.height - iconCard.barH + 4
            width: 48
            height: 26
            Rectangle {
                anchors.fill: parent
                radius: 13
                color: host.iconSearchMode ? "transparent" : host.paperLo
            }
            Text {
                anchors.centerIn: parent
                text: "表情"
                color: host.iconSearchMode ? host.ink3 : host.ink
                font.family: host.uiFont
                font.pixelSize: 10
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: { host.iconSearchMode = false
                             host.iconQuery = ""
                             iconSearch.text = "" }
            }
        }

        // 搜索：按名字（红色史莱姆）或编号（100）过滤
        // 位置照 QQ——点"搜索"页签后，框出现在面板最上面，下面是空的结果区
        Rectangle {
            objectName: "iconSearchBox"
            visible: host.iconSearchMode
            x: iconCard.padX
            y: 10
            width: iconCard.width - iconCard.padX * 2
            height: 28
            radius: 14
            color: host.paperLo
            border.width: 1
            border.color: iconSearch.activeFocus ? host.amber : host.hairline
            Behavior on border.color { ColorAnimation { duration: 120 } }
            // 放大镜（QQ 的搜索框左边就是这个）
            Item {
                x: 11
                anchors.verticalCenter: parent.verticalCenter
                width: 13
                height: 13
                Rectangle {
                    x: 0
                    y: 1
                    width: 9
                    height: 9
                    radius: 4.5
                    color: "transparent"
                    border.width: 1
                    border.color: host.ink3
                }
                Rectangle {
                    x: 8
                    y: 10
                    width: 6
                    height: 1
                    color: host.ink3
                    rotation: 45
                    transformOrigin: Item.Left
                }
            }
            Text {
                visible: iconSearch.text.length === 0
                anchors.left: parent.left
                anchors.leftMargin: 30
                anchors.verticalCenter: parent.verticalCenter
                text: "搜索表情"
                color: host.ink3
                font.family: host.uiFont
                font.pixelSize: 10
            }
            TextInput {
                id: iconSearch
                objectName: "iconSearch"
                anchors.left: parent.left
                anchors.leftMargin: 30
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                height: 20
                verticalAlignment: TextInput.AlignVCenter
                color: host.ink
                font.family: host.uiFont
                font.pixelSize: 10
                selectByMouse: true
                clip: true
                // 双向：打字 → iconQuery；外面（预览/测试）改 iconQuery → 框里跟着变
                text: host.iconQuery
                onTextChanged: host.iconQuery = text
                Keys.onEscapePressed: host.iconPicker = false
            }
        }

        // 一个种族一块：标题（类名 + 张数）+ 这一类的缩略图
        // 用户："要有种族的标题"、"一个种族放一行"、"单个怪不要名字"
        Flickable {
            objectName: "iconFlick"
            x: iconCard.padX
            y: host.iconSearchMode ? 48 : 8
            width: iconCard.width - iconCard.padX * 2
            height: Math.max(40, iconCard.height - y - iconCard.barH)
            contentWidth: width
            contentHeight: iconColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: iconColumn
                width: parent.width
                spacing: 12

                Repeater {
                    model: host.iconGroups()
                    delegate: Column {
                        width: iconColumn.width
                        spacing: 5

                        Text {
                            objectName: "iconGroupName"
                            width: parent.width
                            text: modelData.kind + "   "
                                  + (modelData.items || []).length
                            color: host.ink3
                            font.family: host.uiFont
                            font.pixelSize: 10
                        }

                        Grid {
                            id: groupGrid
                            width: parent.width
                            // 格子大小固定，一行能放几个按宽度算
                            columns: Math.max(
                                1, Math.floor((width + spacing)
                                              / (host.iconCellSize + spacing)))
                            spacing: 4

                            Repeater {
                                model: modelData.items || []
                                delegate: Rectangle {
                                    objectName: "iconCell"
                                    width: host.iconCellSize
                                    height: host.iconCellSize
                                    radius: 6
                                    // 照 QQ：格子上不画框，只有"选中的那张"和鼠标下面有点底色
                                    color: host.monIconId === modelData.id
                                           ? "#EFE7D6"
                                           : (cellMouse.containsMouse
                                              ? "#F4F2EC" : "transparent")

                                    Image {
                                        objectName: "iconCellImage"
                                        anchors.centerIn: parent
                                        // 原图宽高 × 同一个倍数：等比，且一定装得下
                                        width: sourceSize.width * host.iconThumbScale
                                        height: sourceSize.height * host.iconThumbScale
                                        source: modelData && modelData.url
                                                ? modelData.url : ""
                                        fillMode: Image.Stretch
                                        smooth: host.iconThumbSmooth
                                        // 小图、还带缓存：同步加载反而干净
                                        // （异步时一改搜索词就刷屏 "QQuickPixmap: connectFinished"）
                                        asynchronous: false
                                    }
                                    MouseArea {
                                        id: cellMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: host.pickIcon(modelData.id)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
