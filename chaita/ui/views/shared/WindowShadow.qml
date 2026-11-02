import QtQuick
import QtQuick.Effects
import "."

// 子窗口的灰底 + 外投影：垫在窗口最底下，大小和窗口里那张灰底卡片（`anchors.fill: 卡片`）一样。
// 和主窗口同一套（canvas 灰 + 向下 3px 的软阴影），所以子窗口的卡片外面要留
// `Theme.windowInset` 那么宽的透明边，阴影才画得出来。
Rectangle {
    radius: 10
    color: Theme.canvas
    layer.enabled: true
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: Theme.windowShadow
        shadowBlur: 1.0
        shadowVerticalOffset: 3
        shadowHorizontalOffset: 0
    }
}
