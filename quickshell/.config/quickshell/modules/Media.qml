import Quickshell
import Quickshell.Services.Mpris
import QtQuick
import ".."

// Whatever is playing, over MPRIS. Click toggles, wheel skips tracks — the same
// thing the XF86Audio keys do, without needing playerctl in the loop.
Item {
    id: root

    // First player that is actually playing, else the first that exists, so a
    // paused Spotify still shows rather than the bar going blank.
    readonly property var player: {
        const all = Mpris.players.values;
        return all.find(p => p.isPlaying) ?? all[0] ?? null;
    }

    readonly property string title: player?.trackTitle ?? ""

    visible: title !== ""
    implicitWidth: visible ? Math.min(280, label.implicitWidth + 20) : 0
    implicitHeight: parent ? parent.height : Theme.barHeight

    Rectangle {
        anchors.fill: parent
        color: mouse.containsMouse ? Theme.panel : "transparent"
    }

    Text {
        id: label
        anchors.centerIn: parent
        width: Math.min(implicitWidth, root.width - 20)
        text: (root.player?.isPlaying ? " " : " ") + root.title + (root.player?.trackArtist ? " — " + root.player.trackArtist : "")
        color: root.player?.isPlaying ? Theme.green : Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
        elide: Text.ElideRight
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true

        onClicked: if (root.player?.canTogglePlaying) root.player.togglePlaying()

        onWheel: wheelEvent => {
            if (!root.player) return;
            if (wheelEvent.angleDelta.y > 0) root.player.next();
            else root.player.previous();
        }
    }
}
