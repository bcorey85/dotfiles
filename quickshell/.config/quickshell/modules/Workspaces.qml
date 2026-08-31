import Quickshell.Hyprland
import QtQuick
import QtQuick.Layouts
import ".."

RowLayout {
    spacing: 0

    Repeater {
        model: 9

        Item {
            id: ws
            readonly property int wsId: index + 1
            readonly property var hyprWs: Hyprland.workspaces.values.find(w => w.id === wsId)
            readonly property bool isActive: Hyprland.focusedWorkspace?.id === wsId

            Layout.fillHeight: true
            implicitWidth: num.implicitWidth + 16

            Rectangle {
                anchors.fill: parent
                color: mouse.containsMouse ? Theme.panel : "transparent"
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 2
                color: Theme.accent
                visible: ws.isActive
            }

            Text {
                id: num
                anchors.centerIn: parent
                text: ws.wsId
                color: ws.isActive ? Theme.accent : (ws.hyprWs ? Theme.fg : Theme.muted)
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSize
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
