import Quickshell
import Quickshell.Widgets
import QtQuick

// A notification's own image (screenshot, album art) if it sent one, else the
// sending app's themed icon. Collapses to zero width when it has neither.
Item {
    id: root

    property string image: ""
    property string appIcon: ""

    readonly property bool hasImage: image !== ""
    readonly property bool hasIcon: hasImage || appIcon !== ""

    visible: hasIcon
    width: hasIcon ? 32 : 0
    height: 32

    Image {
        anchors.fill: parent
        visible: root.hasImage
        source: root.image
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: 32
        sourceSize.height: 32
    }

    IconImage {
        anchors.fill: parent
        visible: !root.hasImage && root.hasIcon
        source: Quickshell.iconPath(root.appIcon, true)
    }
}
