import Quickshell
import QtQuick
import QtQuick.Layouts
import "modules"

// Module order mirrors waybar's config.jsonc so the A/B is like-for-like.
PanelWindow {
    id: bar
    required property var modelData

    screen: modelData

    // This is the bar now: top edge with a reserved strip, same geometry waybar
    // had. QS_BAR_EDGE=bottom and QS_BAR_EXCLUSIVE=0 put it back in the
    // floating A/B position for running it beside another bar.
    readonly property bool atTop: Quickshell.env("QS_BAR_EDGE") !== "bottom"

    anchors.top: atTop
    anchors.bottom: !atTop
    anchors.left: true
    anchors.right: true
    implicitHeight: Theme.barHeight
    exclusiveZone: Quickshell.env("QS_BAR_EXCLUSIVE") === "0" ? 0 : Theme.barHeight
    color: Theme.bg

    Rectangle {
        anchors.top: bar.atTop ? undefined : parent.top
        anchors.bottom: bar.atTop ? parent.bottom : undefined
        width: parent.width
        height: 2
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 0

        Workspaces {
            Layout.fillHeight: true
        }

        WindowTitle {
            Layout.fillWidth: true
            Layout.maximumWidth: 400
        }

        Item { Layout.fillWidth: true }

        Clock {}

        Item { Layout.fillWidth: true }

        Media {}
        IdleInhibitor {}
        Volume {}
        Bt {}
        Net {}
        SysStats { Layout.fillHeight: true }
        Battery {}
        NotifCenter {}
        Tray { Layout.leftMargin: 8 }
    }
}
