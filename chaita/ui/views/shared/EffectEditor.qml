import QtQuick
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 资源效果的那一栏：一段一条「属性 + 加减号 + 数字框」。
// 配色/字体在上一层：views/shared/Theme.qml（qmldir 里注册成单例）
import ".."

// 资源效果编辑：一段一条，**每段都能单独改数值**。
//
// 用户："宝石加的属性要写死，加的数值要能改"、"黄宝石每个值都要能改"。
// 所以这里既不是一整句只读文字，也不是一个大输入框——是"段"的列表：
//   攻击力  +  [ 1 ▲▼]
//   防御力  +  [ 1 ▲▼]
//   魔防    +  [ 2 ▲▼]
//
// 使用方给两样东西：`parts`（`controller.itemEffectPartList(effect)`）和
// `fieldName`（决定 objectName，测试按它找）。改完发 `partChanged(index, value)`，
// 拼回去的规则只在 `iteminfo.effect_with_part` 一处。
Column {
    id: editor

    // `[{label, sign, digits}]`，从 controller.itemEffectPartList 来
    property var parts: []
    // objectName 前缀：第 1 段用原名（`xxxLabel` / `xxxSign` / `xxx`），
    // 第 2 段起加序号（`xxxLabel1`…），这样老测试按原名还能找到第一段
    property string fieldName: ""

    // 第 index 段改成了 value（松手/回车时一次）
    signal partChanged(int index, string value)

    function partName(base, index) {
        return index === 0 ? base : base + index
    }

    width: parent ? parent.width : implicitWidth
    spacing: 2

    // 同一条里的几段，属性宽度取最宽那个，数字列才对得齐（美观：能对齐的必须对齐）
    readonly property real labelWidth: {
        var widest = 0
        for (var i = 0; i < editor.parts.length; i++)
            widest = Math.max(widest, String(
                (editor.parts[i] || {}).label || "").length)
        return Math.min(96, Math.max(20, widest * 10 + 2))
    }

    Repeater {
        model: editor.parts

        delegate: Row {
            id: partRow
            width: editor.width
            height: 20
            spacing: 4

            readonly property var part: modelData || ({})

            // 属性那截：写死的字（"攻击力"），不给改
            Text {
                objectName: editor.partName(editor.fieldName + "Label", index)
                width: Math.min(editor.labelWidth,
                                Math.max(20, parent.width - signText.width
                                         - stepper.width - parent.spacing * 2))
                height: parent.height
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                text: partRow.part.label || ""
                color: Theme.ink2
                font.family: Theme.uiFont
                font.pixelSize: 10
            }
            // 加号（减号）：也是写死的，跟着属性走
            Text {
                id: signText
                objectName: editor.partName(editor.fieldName + "Sign", index)
                visible: String(partRow.part.digits === undefined
                                ? "" : partRow.part.digits) !== ""
                height: parent.height
                verticalAlignment: Text.AlignVCenter
                text: partRow.part.sign || ""
                color: Theme.ink3
                font.family: Theme.uiFont
                font.pixelSize: 10
            }
            // 数字：窄窄一小条，带上下箭头（箭头只在调整时露出来）
            NumberStepper {
                id: stepper
                width: 34
                height: 20
                fieldName: editor.partName(editor.fieldName, index)
                text: partRow.part.digits === undefined
                      ? "" : String(partRow.part.digits)
                visible: String(partRow.part.digits === undefined
                                ? "" : partRow.part.digits) !== ""
                onCommitted: function (value) {
                    editor.partChanged(index, value)
                }
            }
        }
    }
}
