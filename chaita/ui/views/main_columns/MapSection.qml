import QtQuick
import "../shared"
import "../map_view"

// 地图那一张卡：标题 + 读取按钮 + 地图本体（侧栏切层、一层大图、底下一排操作）。
//
// 地图只画**这一层**，但画得大：左边侧栏快速切层、右边大图，
// 其余层压在大图后面只露一角（用户 2026-10-30）。
Card {
    id: section
    objectName: "mapSectionCard"

    // 归属：主窗口
    property var host

    // 地图卡片在场景里的下沿：「这一层」小窗默认开在它下面，别盖住地图本身
    function mapBottom() {
        return mapCard.mapToItem(null, 0, mapCard.height).y
    }

    SectionHead {
        width: parent.width
        key: "map"
        title: host.mapCollapsed
               ? "地图  " + host.floorList.length + " 层" : "地图"
        collapsed: host.mapCollapsed
        onToggled: host.toggleMapSection()

        Text {
            id: readTipText
            objectName: "readTip"
            anchors.verticalCenter: parent.verticalCenter
            text: host.readTip
            color: Theme.ink3
            font.family: Theme.monoFont
            font.pixelSize: 10
            elide: Text.ElideRight
            width: Math.min(readTipText.implicitWidth, 90)
            horizontalAlignment: Text.AlignRight
            visible: text !== "" && host.floorList.length > 0
        }
        // 读取（只读地图）：挨着地图标题，不在对话框里
        ReadBtn {
            objectName: "readMap"
            host: section.host
            mode: "map"
            busyName: "mapBusyDot"
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // 出错时那句话就贴在标题下面（不占位时高度为 0）
    Text {
        objectName: "errorText"
        width: parent.width
        height: host.notice === "" ? 0 : 18
        visible: host.notice !== ""
        verticalAlignment: Text.AlignVCenter
        text: host.notice
        color: Theme.danger
        font.family: Theme.uiFont
        font.pixelSize: 11
        elide: Text.ElideRight
    }

    Item { width: parent.width; height: 4 }

    MapPanel {
        id: mapCard
        host: section.host
    }
    Text {
        width: parent.width
        height: visible ? 34 : 0
        visible: host.floorList.length === 0 && !host.mapCollapsed
        text: "还没有地图。点这栏的「读取」，一层一层记进来。"
        color: Theme.ink3
        font.family: Theme.uiFont
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }
}
