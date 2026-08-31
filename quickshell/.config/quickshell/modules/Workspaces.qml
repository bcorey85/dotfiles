import Quickshell.Hyprland
import QtQuick
import QtQuick.Layouts
import ".."

// An Item wrapping the layout, not a bare RowLayout: the sliding indicator has
// to be anchored across the whole strip, and anchors on a direct child of a
// layout are undefined behavior.
Item {
    id: root
    implicitWidth: row.implicitWidth

    readonly property int activeId: Hyprland.focusedWorkspace?.id ?? 0

    // One indicator that slides, rather than nine that blink on and off.
    readonly property Item activeItem: activeId >= 1 && activeId <= 9
        ? repeater.itemAt(activeId - 1)
        : null

    RowLayout {
        id: row
        anchors.fill: parent
        spacing: 0

        Repeater {
            id: repeater
            model: 9

            Item {
                id: ws
                readonly property int wsId: index + 1
                readonly property var hyprWs: Hyprland.workspaces.values.find(w => w.id === wsId)
                readonly property bool isActive: root.activeId === wsId

                Layout.fillHeight: true
                implicitWidth: num.implicitWidth + 16

                Rectangle {
                    anchors.fill: parent
                    // Never on the active one — the hover wash would paint over
                    // the accent block sitting behind it.
                    color: (mouse.containsMouse && !ws.isActive) ? Theme.panel : "transparent"
                    Behavior on color { ColorAnimation { duration: 140; easing.type: Easing.OutCubic } }
                }

                Text {
                    id: num
                    anchors.centerIn: parent
                    text: ws.wsId
                    // On the accent block, so it inverts to the bar ground.
                    color: ws.isActive ? Theme.bg : (ws.hyprWs ? Theme.fg : Theme.muted)
                    font.bold: ws.isActive
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize

                    Behavior on color { ColorAnimation { duration: 140; easing.type: Easing.OutCubic } }
                }

                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    hoverEnabled: true
                    // Hyprland 0.56 lua config evals the dispatch argument, so the
                    // legacy "workspace N" string is a syntax error.
                    onClicked: Hyprland.dispatch("hl.dsp.focus({ workspace = " + ws.wsId + " })")
                }
            }
        }
    }

    // Filled block behind the active number, not an underline — a 2px rule at
    // the bar's edge is nearly invisible on a dark ground. z:-1 keeps it behind
    // the digits, which invert onto it.
    Rectangle {
        z: -1
        anchors.verticalCenter: parent.verticalCenter
        height: parent.height - 8
        radius: 4
        color: Theme.accent
        visible: root.activeItem !== null
        x: root.activeItem ? root.activeItem.x : 0
        width: root.activeItem ? root.activeItem.width : 0

        Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 140 } }
    }
}
