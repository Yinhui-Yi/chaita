import QtQuick
import QtQuick.Controls.Basic
import "."

// 一格坐标（"2层 3,4"）：**点一下就能改，可以直接粘一个坐标进来**。
//
// 用户 2026-10-30："楼层位置坐标显示两个当前坐标和出口坐标，可以通过粘贴修改坐标"。
// 用户 2026-10-31："坐标加层数！！！！！！！！" —— 所以显示时把层数写在前面；
// 粘进来的东西只认**最后两个数字**，所以"2层 3,4"整个粘回任何一个坐标格都能用。
// 用户 2026-10-31："粘贴完坐标怎么点空白不退出" —— 现在点窗口空白也会收起来
// （宿主把 `closeTick` 加一，这里就等同按了回车）。
//
// 坐标对外一律**0 开始**（和 controller 一致），显示按 1 开始（和人话"第3行第4列"一致）。
Item {
    id: field

    // 现在这一格（-1 = 没标）
    property int row: -1
    property int col: -1
    // 没标时显示什么
    property string placeholder: "没标"
    // 标了要不要写成 "2层 3,4"（层号由宿主给）
    property string prefix: ""
    property int labelSize: 8
    // 宿主点空白时把它加一：等同于按回车（收起 + 生效）
    property int closeTick: 0
    onCloseTickChanged: field.commitNow()

    // 第三个数是"粘进来的那截层数"（"3层" / "通天塔3"）；没写层数就是空串。
    // 出口那一格拿它直接定"通到哪一层"（用户 2026-10-31："楼梯粘贴出来怎么不带层数"）。
    signal committed(int row, int col, string floorText)
    // 谁在编辑：宿主拿它判断"点空白要不要收起来"（点在输入框自己身上不算）
    signal opened(var who)
    signal closed(var who)

    objectName: "coordField"
    implicitWidth: Math.max(28, label.implicitWidth)
    implicitHeight: 14

    readonly property bool editing: editor.visible

    // "3层 2,4" / "2,4" / "2 4" / "2，4" / "2、4" → (1,3)（换成 0 开始）；认不出返回 null
    // 坐标只认**最后两个数字**；前面那截当层数带出来（"→3层 6,7" → 层数 "3层"）。
    function parse(text) {
        var raw = String(text || "")
        var numbers = raw.match(/\d+/g)
        if (!numbers || numbers.length < 2)
            return null
        var row = parseInt(numbers[numbers.length - 2], 10)
        var col = parseInt(numbers[numbers.length - 1], 10)
        if (isNaN(row) || isNaN(col))
            return null
        if (row < 1 || col < 1 || row > 13 || col > 13)
            return null
        // 层数 = 最后一个"行号"之前的那些字；把头尾的箭头/标点削掉
        var at = raw.lastIndexOf(numbers[numbers.length - 2])
        var head = raw.substring(0, at)
        head = head.replace(/^[^0-9A-Za-z\u4e00-\u9fa5]+/, "")
        head = head.replace(/[^0-9A-Za-z\u4e00-\u9fa5]+$/, "")
        return { "row": row - 1, "col": col - 1, "floor": head.trim() }
    }

    function display() {
        if (field.row < 0 || field.col < 0)
            return ""
        return field.prefix + (field.row + 1) + "," + (field.col + 1)
    }

    // 打开输入框：只填坐标本身（层数是显示用的，不用改）
    function open() {
        editor.text = field.row >= 0 && field.col >= 0
                ? (field.row + 1) + "," + (field.col + 1) : ""
        editor.visible = true
        editor.forceActiveFocus()
        editor.selectAll()
        field.opened(field)
    }

    // 收起并生效（回车 / 点空白 / Esc 之外的地方都不丢输入）
    function commitNow() {
        if (!editor.visible)
            return
        var at = field.parse(editor.text)
        editor.visible = false
        field.closed(field)
        if (at === null)
            return
        field.committed(at.row, at.col, String(at.floor || ""))
    }

    Text {
        id: label
        anchors.fill: parent
        visible: !editor.visible
        verticalAlignment: Text.AlignVCenter
        text: field.display() !== "" ? field.display() : field.placeholder
        color: field.display() !== "" ? Theme.ink : Theme.ink3
        font.family: Theme.uiFont
        font.pixelSize: field.labelSize
    }

    MouseArea {
        anchors.fill: parent
        anchors.margins: -3
        enabled: !editor.visible
        cursorShape: Qt.IBeamCursor
        onClicked: field.open()
    }

    TextField {
        id: editor
        objectName: "coordEditor"
        // 输入框比那一格宽：一行装得下"2层 12,12"，不然改到一半就被切掉
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(parent.width, parent.implicitWidth + 24,
                        implicitWidth + 12)
        height: parent.height + 4
        visible: false
        selectByMouse: true
        verticalAlignment: TextInput.AlignVCenter
        background: Rectangle { color: Theme.paperHi; radius: 4
                                border.width: 1; border.color: Theme.amber }
        color: Theme.ink
        font.family: Theme.uiFont
        font.pixelSize: field.labelSize
        // 贴进去就认（用户："可以通过粘贴修改坐标"），回车/失焦生效
        onEditingFinished: field.commitNow()
        Keys.onEscapePressed: {
            editor.visible = false
            field.closed(field)
        }
    }
}
