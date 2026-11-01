import QtQuick
import "../shared"

// 读取记录那一张卡（任务队列）：每点一次「读取」就是一条任务，可以并行，
// 这里逐条列出来，跑着的能取消、失败的能重试。没有任务时整张卡不占位。
Card {
    id: section

    // 归属：主窗口
    property var host

    visible: host.tasksView.length > 0

    SectionHead {
        objectName: "taskSection"
        width: parent.width
        key: "task"
        title: "读取记录"
        collapsible: false

        Text {
            objectName: "taskAgg"
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
            color: Theme.ink3
            font.family: Theme.monoFont
            font.pixelSize: 10
        }
    }
    Item { width: parent.width; height: 4 }

    Repeater {
        model: host.tasksView
        delegate: Item {
            objectName: "taskRow"
            width: parent.width
            height: host.tasksView.length === 0 ? 0 : 30

            // 状态点：跑着=强调蓝、成功=墨、失败=红、取消=浅灰
            Text {
                objectName: "taskDot"
                x: 2
                anchors.verticalCenter: parent.verticalCenter
                text: "●"
                color: modelData.state === "running" ? Theme.accent
                     : (modelData.state === "failed" ? Theme.danger
                     : (modelData.state === "done" ? Theme.ink2 : Theme.ink3))
                font.pixelSize: 9
            }
            // 这次读取用的那张截图（点开看大图）；没有截图就空着，不留框
            Rectangle {
                objectName: "taskThumb"
                x: 16
                width: 22
                height: 22
                radius: 4
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.tile
                border.width: 1
                border.color: Theme.hairline
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
                x: 44
                width: 24
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.modeLabel
                visible: modelData.modeLabel !== ""
                color: Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 10
            }
            Text {
                objectName: "taskText"
                anchors.left: parent.left
                anchors.leftMargin: 72
                anchors.right: taskTail.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.text
                color: modelData.state === "failed" ? Theme.danger : Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 11
                elide: Text.ElideRight
            }
            Row {
                id: taskTail
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Text {
                    objectName: "taskElapsed"
                    visible: modelData.elapsed >= 0
                    text: modelData.elapsed >= 0
                          ? modelData.elapsed + "s" : ""
                    color: Theme.ink3
                    font.family: Theme.monoFont
                    font.pixelSize: 10
                }
                Text {
                    objectName: "taskCancel"
                    visible: modelData.canCancel
                    text: "取消"
                    color: taskCancelMouse.containsMouse
                           ? Theme.danger : Theme.ink3
                    font.family: Theme.uiFont
                    font.pixelSize: 11
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
                           ? Theme.accent : Theme.ink2
                    font.family: Theme.uiFont
                    font.pixelSize: 11
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
                color: Theme.hairline
            }
        }
    }
}
