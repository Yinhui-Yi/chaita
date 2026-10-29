import QtQuick
// 先看 docs/UI_MAP.md：哪份文件画哪个界面、状态在谁身上、objectName 怎么起。
// 这一份 = 链上的箭头（伤害计算和路线链共用同一个）。
// 配色/字在上一层：views/shared/qmldir 里注册的 Theme 单例
import ".."

// 链上的"→"：两条短线拼出来的 ">"。
//
// 原来是伤害计算里的一个行内组件（用户："箭头太丑了，而且不明显" —— 以前是一个
// 字号 9 的 "→"，又细又看不清；这里粗一档、鼠标移上去有药丸底和琥珀色）。
// 路线链也要一条一模一样的链，所以搬到这里 —— 一处实现，两处共用。
Item {
    id: arrow
    signal clicked()
    // 能点 = 这里可以插一格（伤害计算）；路线链的格子是走出来的，不在这里插，
    // 所以那边传 clickable: false（没有悬停底色，也不吃鼠标）
    property bool clickable: true

    width: 14
    height: 26

    Rectangle {
        anchors.centerIn: parent
        width: arrow.width
        height: 18
        radius: 4
        color: arrow.clickable && arrowMouse.containsMouse
               ? Theme.paperLo : "transparent"
    }
    Item {
        anchors.centerIn: parent
        width: 9
        height: 14
        Rectangle {
            objectName: "chainArrowLeg"
            x: 1; y: parent.height / 2 - 0.8
            width: 7; height: 1.6; radius: 0.8
            color: arrow.clickable && arrowMouse.containsMouse
                   ? Theme.amber : Theme.ink2
            transform: Rotation {
                origin.x: 7; origin.y: 0.8; angle: -35
            }
        }
        Rectangle {
            objectName: "chainArrowLeg"
            x: 1; y: parent.height / 2 - 0.8
            width: 7; height: 1.6; radius: 0.8
            color: arrow.clickable && arrowMouse.containsMouse
                   ? Theme.amber : Theme.ink2
            transform: Rotation {
                origin.x: 7; origin.y: 0.8; angle: 35
            }
        }
    }
    MouseArea {
        id: arrowMouse
        anchors.fill: parent
        enabled: arrow.clickable
        hoverEnabled: arrow.clickable
        cursorShape: arrow.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: arrow.clicked()
    }
}
