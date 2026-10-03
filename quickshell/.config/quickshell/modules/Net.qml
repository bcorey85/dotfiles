import Quickshell
import Quickshell.Networking
import QtQuick
import ".."

// Left-click opens a network list: click a known or open network to connect,
// click the connected one to disconnect, click a new secured one to type its
// password. The scanner only runs while the list is open.
BarItem {
    id: root

    readonly property var dev: {
        const list = Networking.devices.values;
        // Prefer a connected device; wifi wins over wired only if wired is down.
        return list.find(d => d.connected && d.type === DeviceType.Wifi)
            ?? list.find(d => d.connected)
            ?? null;
    }
    readonly property var wifiDev: Networking.devices.values.find(d => d.type === DeviceType.Wifi) ?? null
    readonly property var wifiNet: dev?.networks?.values?.find(n => n.connected) ?? null
    readonly property var wifiNetworks: (wifiDev?.networks?.values ?? [])
        .filter(n => n.name !== "")
        .sort((a, b) => (b.connected - a.connected) || (b.signalStrength - a.signalStrength))
        .slice(0, 12)

    // Network awaiting a password, and the last failure to show under the list.
    property var pskTarget: null
    property string failure: ""

    text: {
        if (!dev) return "  Disconnected";
        if (dev.type === DeviceType.Wifi && wifiNet)
            return "  WiFi " + Math.round(wifiNet.signalStrength * 100) + "%";
        return "  " + (dev.address || dev.name);
    }
    color: dev ? Theme.teal : Theme.red
    clickable: true
    onClicked: popup.toggle()

    function choose(network) {
        failure = "";
        if (network.connected) {
            network.disconnect();
        } else if (network.known || network.security === WifiSecurityType.Open) {
            network.connect();
        } else {
            pskTarget = network;
            pskInput.text = "";
            pskInput.forceActiveFocus();
        }
    }

    function submitPsk() {
        if (!pskTarget || pskInput.text === "") return;
        pskTarget.connectWithPsk(pskInput.text);
        pskInput.text = "";
        pskTarget = null;
    }

    BarPopup {
        id: popup
        anchor.window: QsWindow.window
        rightAlignTo: root
        anchor.rect.y: root.y + root.height
        implicitWidth: 300
        implicitHeight: content.implicitHeight + 24

        onVisibleChanged: {
            if (root.wifiDev) root.wifiDev.scannerEnabled = visible;
            if (!visible) {
                root.pskTarget = null;
                root.failure = "";
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Theme.panel
            border.color: Theme.border
            border.width: 1
            radius: 8

            Column {
                id: content
                anchors.centerIn: parent
                width: parent.width - 24
                spacing: 4

                Item {
                    width: content.width
                    height: 26

                    Rectangle {
                        anchors.fill: parent
                        color: toggleMouse.containsMouse ? Theme.bg : "transparent"
                        radius: 4
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        leftPadding: 6
                        text: Networking.wifiEnabled ? "󰖩  Wi-Fi on" : "󰖪  Wi-Fi off"
                        color: Networking.wifiEnabled ? Theme.teal : Theme.muted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize
                    }

                    MouseArea {
                        id: toggleMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: Networking.wifiEnabled = !Networking.wifiEnabled
                    }
                }

                Rectangle {
                    visible: Networking.wifiEnabled
                    width: content.width
                    height: 1
                    color: Theme.border
                }

                Text {
                    visible: Networking.wifiEnabled && root.wifiNetworks.length === 0
                    leftPadding: 6
                    text: "Scanning…"
                    color: Theme.muted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize
                }

                Repeater {
                    model: Networking.wifiEnabled ? root.wifiNetworks : []

                    Item {
                        id: row
                        required property var modelData
                        width: content.width
                        height: 26

                        Connections {
                            target: row.modelData
                            function onConnectionFailed(reason) {
                                root.failure = row.modelData.name + ": " + ConnectionFailReason.toString(reason);
                            }
                        }

                        Rectangle {
                            anchors.fill: parent
                            color: rowMouse.containsMouse ? Theme.bg : "transparent"
                            radius: 4
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.right: strength.left
                            anchors.verticalCenter: parent.verticalCenter
                            leftPadding: 6
                            elide: Text.ElideRight
                            text: {
                                const n = row.modelData;
                                const lock = n.security === WifiSecurityType.Open ? "  " : "󰌾 ";
                                const busy = n.stateChanging ? " …" : "";
                                return lock + n.name + busy;
                            }
                            color: row.modelData.connected ? Theme.teal : Theme.fg
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSize
                        }

                        Text {
                            id: strength
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            rightPadding: 6
                            text: Math.round(row.modelData.signalStrength * 100) + "%"
                            color: Theme.muted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSize
                        }

                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: root.choose(row.modelData)
                        }
                    }
                }

                Rectangle {
                    visible: root.pskTarget !== null
                    width: content.width
                    height: 28
                    color: Theme.bg
                    border.color: Theme.border
                    border.width: 1
                    radius: 4

                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        verticalAlignment: Text.AlignVCenter
                        visible: pskInput.text === ""
                        text: "Password for " + (root.pskTarget?.name ?? "")
                        color: Theme.muted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize
                    }

                    TextInput {
                        id: pskInput
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        verticalAlignment: TextInput.AlignVCenter
                        echoMode: TextInput.Password
                        color: Theme.fg
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize
                        clip: true
                        onAccepted: root.submitPsk()
                        Keys.onEscapePressed: root.pskTarget = null
                    }
                }

                Text {
                    visible: root.failure !== ""
                    width: content.width
                    leftPadding: 6
                    wrapMode: Text.Wrap
                    text: root.failure
                    color: Theme.red
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize
                }
            }
        }
    }
}
