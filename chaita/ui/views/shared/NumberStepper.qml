import QtQuick
import QtQuick.Controls.Basic
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 一个数字框 + 上下两个箭头（像 Word 那个字号框）。
// 配色/字体在上一层：views/shared/Theme.qml（qmldir 里注册成单例）
import ".."

// 数字框 + 上下箭头：点一下 ±1，按住连加/连减，也能直接打字。
//
// 用户："调整资源的数值和数量的窗口能不能做的像 word 改字号一样有两个箭头
// 分别表示增和减"。
//
// 三条规矩：
//   1. **松手才报**（`committed`）—— 按住连加时中间那几十次不写盘，
//      不然每 70ms 就存一次会话文件。
//   2. 框里只留数字/小数点；加减号是外面写死的只读字，这里改不动。
//   3. **箭头平时不占视觉**：鼠标移上来或框拿到焦点才出现（用户 2026-10-28：
//      "箭头只有调整时才显示"）；位置留好了，出现时不跳。
Item {
    id: spinner

    // 测试/调试按名字找：整个框 = fieldName + "Box"，里面的输入框 = fieldName
    objectName: spinner.fieldName + "Box"

    // 现在显示的数字（字符串；空 = 还没数值）
    property string text: ""
    // 一次加/减多少
    property int step: 1
    property int minValue: 0
    property int maxValue: 9999
    // 测试/调试按名字找：框 = fieldName，箭头 = fieldName + "Up" / "Down"
    property string fieldName: ""
    // 改完了（松手 / 打完字回车或点别处）才发，值 = 归一化后的数字
    signal committed(string text)

    // 一个数字 + 两个箭头的位置就够了；别把框拉成一整条（用户："调整框怎么这么长"）
    implicitWidth: 34
    implicitHeight: 20

    // 箭头只在这两种时候出现：鼠标在这框上 / 正在改它
    readonly property bool arrowsShown: hover.hovered || field.activeFocus

    // 按住连加/连减：先等 400ms，再每 70ms 一步
    property int holdDir: 1
    property string valueAtPress: ""

    function normalized() {
        return String(field.text).replace(/[^0-9.]/g, "")
    }

    function bump(dir) {
        var n = parseInt(spinner.normalized() || "0", 10)
        if (isNaN(n))
            n = 0
        n += dir * spinner.step
        n = Math.max(spinner.minValue, Math.min(spinner.maxValue, n))
        field.text = String(n)
    }

    // 报一次（值没变就不报：点了箭头又点回来，不该多存一遍）
    function settle() {
        var clean = spinner.normalized()
        if (clean !== spinner.valueAtPress)
            spinner.committed(clean)
        spinner.valueAtPress = clean
    }

    function startHold(dir) {
        spinner.valueAtPress = spinner.normalized()
        spinner.holdDir = dir
        spinner.bump(dir)
        holdDelay.restart()
    }

    function stopHold() {
        holdDelay.stop()
        holdRepeat.stop()
        spinner.settle()
    }

    Timer {
        id: holdDelay
        interval: 400
        onTriggered: holdRepeat.start()
    }
    Timer {
        id: holdRepeat
        interval: 70
        repeat: true
        onTriggered: spinner.bump(spinner.holdDir)
    }

    HoverHandler {
        id: hover
    }

    // 底：平时只有一条很淡的线（看得出能改，又不抢眼），悬停加底色，聚焦变琥珀
    Rectangle {
        anchors.fill: parent
        radius: 5
        color: (field.activeFocus || hover.hovered) ? Theme.paperLo : "transparent"
        border.width: 1
        border.color: field.activeFocus ? Theme.amber : Theme.hairline
        Behavior on border.color { ColorAnimation { duration: 120 } }
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    TextField {
        id: field
        objectName: spinner.fieldName
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: arrows.left
        background: null
        padding: 0
        leftPadding: 4
        rightPadding: 0
        horizontalAlignment: TextInput.AlignLeft
        verticalAlignment: TextInput.AlignVCenter
        color: Theme.ink
        font.family: Theme.monoFont
        font.pixelSize: 10
        selectByMouse: true
        text: spinner.text
        // 只收数字和小数点
        onTextChanged: {
            var clean = String(text).replace(/[^0-9.]/g, "")
            if (clean !== String(text)) {
                text = clean
                return
            }
        }
        onEditingFinished: {
            text = spinner.normalized()
            spinner.settle()
        }
    }

    // 两个箭头：上一半加、下一半减。**平时藏着**，鼠标/焦点来了才现
    Item {
        id: arrows
        anchors.right: parent.right
        anchors.rightMargin: 1
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 11
        // 只改透明度、不藏 visible：位置留好，出现时不跳，也一直点得中
        opacity: spinner.arrowsShown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 100 } }

        MouseArea {
            id: upArea
            objectName: spinner.fieldName + "Up"
            width: parent.width
            height: Math.floor(parent.height / 2)
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: spinner.startHold(1)
            onReleased: spinner.stopHold()
            onCanceled: spinner.stopHold()
            Canvas {
                id: upTriangle
                anchors.centerIn: parent
                width: 7
                height: 4
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.fillStyle = upArea.containsMouse ? Theme.amber : Theme.ink3
                    ctx.beginPath()
                    ctx.moveTo(0, height)
                    ctx.lineTo(width, height)
                    ctx.lineTo(width / 2, 0)
                    ctx.closePath()
                    ctx.fill()
                }
                onWidthChanged: requestPaint()
                // 鼠标移上去换个色（箭头小，不改色看不出来能点）
                Connections {
                    target: upArea
                    function onContainsMouseChanged() { upTriangle.requestPaint() }
                }
            }
        }

        MouseArea {
            id: downArea
            objectName: spinner.fieldName + "Down"
            width: parent.width
            height: parent.height - Math.floor(parent.height / 2)
            anchors.bottom: parent.bottom
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: spinner.startHold(-1)
            onReleased: spinner.stopHold()
            onCanceled: spinner.stopHold()
            Canvas {
                id: downTriangle
                anchors.centerIn: parent
                width: 7
                height: 4
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.fillStyle = downArea.containsMouse ? Theme.amber : Theme.ink3
                    ctx.beginPath()
                    ctx.moveTo(0, 0)
                    ctx.lineTo(width, 0)
                    ctx.lineTo(width / 2, height)
                    ctx.closePath()
                    ctx.fill()
                }
                onWidthChanged: requestPaint()
                Connections {
                    target: downArea
                    function onContainsMouseChanged() { downTriangle.requestPaint() }
                }
            }
        }
    }
}
