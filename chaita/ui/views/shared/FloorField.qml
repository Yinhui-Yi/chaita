import QtQuick
import QtQuick.Controls.Basic
import "."

// 一层楼的名字（"2"、"通天塔3"、"2层"都认）：**点一下就能打，回车生效**。
//
// 用户 2026-10-31 骂掉了"点一下换一层"的循环："循环你妈个逼" —— 一千层的塔根本
// 点不过来，而且想跳到哪层得一路点过去。所以这一格和坐标格（`CoordField`）同一个
// 手感：平时是一行字，点开变输入框，打层号回车；清空 = 没选。
// 点窗口空白也会收起来并生效（`closeTick`，用户："粘贴完坐标怎么点空白不退出"）。
Item {
    id: field

    // 现在的值（完整的层名；空 = 没选）
    property string value: ""
    // 没选时显示什么
    property string placeholder: "通到…"
    property int labelSize: 9
    // 值的写法：给了函数就按它显示（比如只显示层号）
    property var showText: null
    // 点开时输入框里填什么：给了函数就用它，没给就用 `value`（完整层名）。
    // **别拿 `showText` 当初值**：那是显示用的，可能带 "→ " 这种装饰，回车提交回来
    // 就变成一个不存在的层名（用户 2026-10-31："楼梯坐标我粘贴后再选中楼层信息就没了"）。
    property var editText: null
    // 宿主点空白时把它加一：等同于按回车
    property int closeTick: 0
    onCloseTickChanged: field.commitNow()

    signal committed(string text)
    // 谁在编辑：宿主拿它判断"点空白要不要收起来"（点在输入框自己身上不算）
    signal opened(var who)
    signal closed(var who)

    objectName: "floorField"
    implicitWidth: Math.max(40, label.implicitWidth)
    implicitHeight: 16

    readonly property bool editing: editor.visible

    function display() {
        var text = String(field.value || "")
        if (text === "")
            return ""
        if (field.showText)
            return String(field.showText(text))
        return text
    }

    function open() {
        // 打开时填**层号**（"2"），不填整套层名：手打的多半就是个数字。
        // 这个"层号"由宿主用 `editText` 给（楼梯那边是 `floorShort`），
        // 绝不能拿显示文字（带 "→ "）来填 —— 见 `editText` 上面的注释。
        var text = String(field.value || "")
        if (text !== "" && field.editText)
            text = String(field.editText(text))
        editor.text = text
        editor.visible = true
        editor.forceActiveFocus()
        editor.selectAll()
        field.opened(field)
    }

    function commitNow() {
        if (!editor.visible)
            return
        var text = String(editor.text || "").trim()
        editor.visible = false
        field.closed(field)
        field.committed(text)
    }

    Text {
        id: label
        anchors.fill: parent
        visible: !editor.visible
        verticalAlignment: Text.AlignVCenter
        text: field.display() !== "" ? field.display() : field.placeholder
        color: field.display() !== "" ? Theme.ink : Theme.amber
        font.family: Theme.uiFont
        font.pixelSize: field.labelSize
        font.bold: field.display() !== ""
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
        objectName: "floorEditor"
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(parent.width, implicitWidth + 12)
        height: parent.height + 4
        visible: false
        selectByMouse: true
        verticalAlignment: TextInput.AlignVCenter
        background: Rectangle { color: Theme.paperHi; radius: 4
                                border.width: 1; border.color: Theme.amber }
        color: Theme.ink
        font.family: Theme.uiFont
        font.pixelSize: field.labelSize
        // 回车/失焦生效（"2" → 由宿主翻成层名；空 = 没选）
        onEditingFinished: field.commitNow()
        Keys.onEscapePressed: {
            editor.visible = false
            field.closed(field)
        }
    }
}
