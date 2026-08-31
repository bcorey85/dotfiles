import Quickshell
import Quickshell.Bluetooth
import QtQuick
import ".."

// Left-click opens an inline device list with connect/disconnect. blueman-manager
// is still there for pairing; this covers the daily case without a foreign window.
Item {
    id: root

    readonly property var adapter: Bluetooth.defaultAdapter
    readonly property var connected: Bluetooth.devices.values.filter(d => d.connected)

    implicitWidth: label.implicitWidth + 20
    implicitHeight: parent ? parent.height : Theme.barHeight

    Rectangle {
        anchors.fill: parent
        color: mouse.containsMouse ? Theme.panel : "transparent"
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: {
            if (!root.adapter?.enabled) return "󰂲";
            if (root.connected.length === 0) return "󰂯";
            const d = root.connected[0];
            return "󰂱 " + d.deviceName + (d.batteryAvailable ? " " + Math.round(d.battery * 100) + "%" : "");
        }
        color: root.adapter?.enabled ? Theme.teal : Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: popup.toggle()
    }

    BarPopup {
        id: popup
        anchor.window: QsWindow.window
        anchor.rect.x: root.x
        anchor.rect.y: root.y + root.height
        implicitWidth: 280
        implicitHeight: Math.max(48, list.implicitHeight + 24)

        Rectangle {
            anchors.fill: parent
            color: Theme.panel
            border.color: Theme.border
            border.width: 1
            radius: 8

            Column {
                id: list
                anchors.centerIn: parent
                width: parent.width - 24
                spacing: 4

                Text {
                    visible: Bluetooth.devices.values.length === 0
                    text: "No devices"
                    color: Theme.muted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize
                }

                Repeater {
                    // Paired devices only — this is not a scanner.
                    model: Bluetooth.devices.values.filter(d => d.paired)

                    Item {
                        required property var modelData
                        width: list.width
                        height: 26

                        Rectangle {
                            anchors.fill: parent
                            color: rowMouse.containsMouse ? Theme.bg : "transparent"
                            radius: 4
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            leftPadding: 6
                            text: (parent.modelData.connected ? "󰂱 " : "󰂯 ") + parent.modelData.deviceName
                            color: parent.modelData.connected ? Theme.teal : Theme.fg
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSize
                        }

                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                const d = parent.modelData;
                                if (d.connected) d.disconnect();
                                else d.connect();
                            }
                        }
                    }
                }
            }
        }
    }
}
