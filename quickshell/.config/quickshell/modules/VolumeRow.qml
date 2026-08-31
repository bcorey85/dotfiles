import QtQuick
import ".."

// One labelled volume slider bound to a pipewire node. Caller keeps the node
// tracked (PwObjectTracker) or its audio stays unbound.
Item {
    id: row

    property string label: ""
    property var node: null

    readonly property var audio: node?.audio ?? null

    implicitHeight: 34

    Text {
        id: name
        anchors.top: parent.top
        width: parent.width - level.width - 8
        text: row.label
        color: Theme.fg
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize - 2
        elide: Text.ElideRight

        MouseArea {
            anchors.fill: parent
            onClicked: if (row.audio) row.audio.muted = !row.audio.muted
        }
    }

    Text {
        id: level
        anchors.top: parent.top
        anchors.right: parent.right
        text: row.audio?.muted ? "muted" : Math.round((row.audio?.volume ?? 0) * 100) + "%"
        color: Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize - 3
    }

    Rectangle {
        id: track
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        width: parent.width
        height: 6
        radius: 3
        color: Theme.border

        Rectangle {
            width: track.width * (row.audio?.volume ?? 0)
            height: parent.height
            radius: 3
            color: row.audio?.muted ? Theme.muted : Theme.orange
        }

        MouseArea {
            anchors.fill: parent
            anchors.margins: -8
            onPositionChanged: mouseEvent => set(mouseEvent.x)
            onPressed: mouseEvent => set(mouseEvent.x)

            function set(x) {
                if (row.audio)
                    row.audio.volume = Math.max(0, Math.min(1, x / track.width));
            }
        }
    }
}
