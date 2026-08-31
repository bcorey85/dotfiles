import Quickshell
import Quickshell.Services.Pipewire
import QtQuick
import ".."

// Left-click mutes, scroll adjusts, right-click opens the mixer: master level,
// per-app streams, and output device switching — the whole reason pavucontrol
// used to be open.
Item {
    id: root

    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var audio: sink?.audio ?? null
    readonly property int pct: audio ? Math.round(audio.volume * 100) : 0
    readonly property bool muted: audio?.muted ?? false

    // Playback streams (apps) and real output devices.
    readonly property var streams: Pipewire.nodes.values.filter(n => n.isStream && n.isSink && n.audio)
    readonly property var outputs: Pipewire.nodes.values.filter(n => !n.isStream && n.isSink)

    // Without a tracker a node's audio properties stay unbound.
    PwObjectTracker {
        objects: [...root.streams, ...root.outputs]
    }

    visible: audio !== null
    implicitWidth: visible ? label.implicitWidth + 20 : 0
    implicitHeight: parent ? parent.height : Theme.barHeight

    Rectangle {
        anchors.fill: parent
        color: mouse.containsMouse ? Theme.panel : "transparent"
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.muted ? "  Muted" : (root.pct >= 66 ? " " : root.pct >= 33 ? " " : " ") + " VOL " + root.pct + "%"
        color: root.muted ? Theme.muted : Theme.orange
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        onClicked: mouseEvent => {
            if (!root.audio) return;
            if (mouseEvent.button === Qt.RightButton) popup.toggle();
            else root.audio.muted = !root.audio.muted;
        }

        onWheel: wheelEvent => {
            if (!root.audio) return;
            const step = wheelEvent.angleDelta.y > 0 ? 0.05 : -0.05;
            root.audio.volume = Math.max(0, Math.min(1, root.audio.volume + step));
        }
    }

    BarPopup {
        id: popup
        anchor.window: QsWindow.window
        rightAlignTo: root
        anchor.rect.y: root.y + root.height
        implicitWidth: 340
        implicitHeight: mixer.implicitHeight + 24

        Rectangle {
            anchors.fill: parent
            color: Theme.panel
            border.color: Theme.border
            border.width: 1
            radius: 8

            Column {
                id: mixer
                anchors.centerIn: parent
                width: parent.width - 24
                spacing: 10

                VolumeRow {
                    width: parent.width
                    label: root.sink?.description ?? "Output"
                    node: root.sink
                }

                Text {
                    visible: root.streams.length > 0
                    text: "Apps"
                    color: Theme.muted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize - 3
                }

                Repeater {
                    model: root.streams

                    VolumeRow {
                        required property var modelData
                        width: mixer.width
                        label: modelData.properties["application.name"] ?? modelData.name
                        node: modelData
                    }
                }

                Text {
                    visible: root.outputs.length > 1
                    text: "Output"
                    color: Theme.muted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize - 3
                }

                Repeater {
                    model: root.outputs.length > 1 ? root.outputs : []

                    Item {
                        id: out
                        required property var modelData
                        readonly property bool current: Pipewire.defaultAudioSink === modelData

                        width: mixer.width
                        height: 22

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width
                            text: (out.current ? "󰄬 " : "   ") + (out.modelData.description ?? out.modelData.name)
                            color: out.current ? Theme.orange : Theme.fg
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSize - 2
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: Pipewire.preferredDefaultAudioSink = out.modelData
                        }
                    }
                }
            }
        }
    }
}
