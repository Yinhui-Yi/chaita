import QtQuick
import QtQuick.Controls.Basic
// 共用件（配色/卡片/按钮）在上一层
import "../shared"

// 主界面中间那一摞卡：上次的记录横幅 + 地图 / 怪物 / 技能 / 读取记录各一张卡。
//
// 主窗口的一块（不是覆盖层）。滚动容器是外面那层 `flick`（Flickable），
// 这里只是它里面的 `Column`；所以外层要 `flick.contentHeight: body.implicitHeight`，
// 那边仍用 id `body` 指过来。
//
// 每张卡自己一个文件（MapSection / MonSection / SkillSection / TaskSection），
// 折叠状态和列表数据都在 host 上，这里只管把它们按顺序摞起来。
Column {
    id: body

    // 归属：主窗口（列表数据、折叠状态、拖动状态都在它身上）
    property var host

    // 主窗口要量的两处位置（要量就问这里，别跨文件摸各张卡的内部 id）
    // 地图卡片在场景里的下沿：「这一层」小窗默认开在它下面，别盖住地图本身
    function mapBottom() {
        return mapSection.mapBottom()
    }

    // 第一行怪在场景里的上沿（-1 = 还没有行）：拖动排序时要把屏幕坐标对上
    function firstRowTop() {
        return monSection.firstRowTop()
    }

    objectName: "contentBody"
    width: host.bodyW
    // 卡与卡之间的缝；不可见的卡（没有任务、没有横幅）Column 会跳过，不留空缝
    spacing: host.gapB
    // 行数/内容变了，窗口高度跟着走（内容决定高度，不留一截空白）

    // ---------- 上次留下的记录：只提示，点「恢复」才加载 ----------
    // 不自动恢复：旧血量/旧钥匙会误导人；层和怪是手工劳动，值得留一份。
    Rectangle {
        objectName: "sessionBar"
        width: body.width
        height: 32
        radius: 8
        color: Theme.accentSoft
        visible: host.sessionHint !== ""

        Text {
            id: sessionText
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 110
            text: "上次的记录：" + host.sessionHint
            color: Theme.ink2
            font.family: Theme.uiFont
            font.pixelSize: 11
            elide: Text.ElideRight
        }
        Text {
            id: sessionRestore
            objectName: "sessionRestore"
            anchors.right: sessionDiscard.left
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: "恢复"
            color: restoreMouse.containsMouse ? Theme.accentHover : Theme.accent
            font.family: Theme.uiFont
            font.pixelSize: 11
            font.bold: true
            MouseArea {
                id: restoreMouse
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.restoreSession()
            }
        }
        Text {
            id: sessionDiscard
            objectName: "sessionDiscard"
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: "忽略"
            color: discardMouse.containsMouse ? Theme.ink : Theme.ink3
            font.family: Theme.uiFont
            font.pixelSize: 11
            MouseArea {
                id: discardMouse
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.discardSession()
            }
        }
    }

    MapSection { id: mapSection; width: body.width; host: body.host }
    MonSection { id: monSection; width: body.width; host: body.host }
    SkillSection { width: body.width; host: body.host }
    TaskSection { width: body.width; host: body.host }
}
