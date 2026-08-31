import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import QtQuick

// On-screen display for the media keys — volume, mic mute, brightness. The
// keybinds still run wpctl/brightnessctl; this only watches the resulting
// state, so there is nothing to keep in sync in hyprland.lua.
PanelWindow {
    id: osd

    // What the last change was, and enough to render it.
    property string icon: ""
    property string label: ""
    property real value: 0
    property bool showValue: true

    // Suppress the OSD for the initial value of every source — otherwise it
    // flashes on login for things nobody touched.
    property bool ready: false

    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource

    PwObjectTracker {
        objects: [osd.sink, osd.source].filter(n => n !== null)
    }

    function flash(icon, label, value, showValue) {
        if (!osd.ready) return;
        osd.icon = icon;
        osd.label = label;
        osd.value = value;
        osd.showValue = showValue ?? true;
        osd.visible = true;
        hide.restart();
    }

    Component.onCompleted: settle.start()

    // One tick after startup every source has reported in; anything after that
    // is a real change.
    Timer {
        id: settle
        interval: 1000
        onTriggered: osd.ready = true
    }

    Timer {
        id: hide
        interval: 1500
        onTriggered: osd.visible = false
    }

    anchors.bottom: true
    margins.bottom: 120
    implicitWidth: 280
    implicitHeight: 72
    exclusiveZone: 0
    color: "transparent"
    visible: false

    Connections {
        target: osd.sink?.audio ?? null

        function onVolumeChanged() {
            const a = osd.sink.audio;
            if (a.muted) return;
            osd.flash("", "Volume", a.volume);
        }

        function onMutedChanged() {
            const a = osd.sink.audio;
            osd.flash(a.muted ? "" : "", a.muted ? "Muted" : "Volume", a.volume);
        }
    }

    Connections {
        target: osd.source?.audio ?? null

        function onMutedChanged() {
            const a = osd.source.audio;
            osd.flash(a.muted ? "" : "", a.muted ? "Mic muted" : "Mic on", 0, false);
        }
    }

    // Brightness lives in sysfs; no backlight (a desktop) leaves this inert.
    property string backlight: ""
    property int backlightMax: 0

    Process {
        running: true
        command: ["sh", "-c", "ls -d /sys/class/backlight/*/ 2>/dev/null | head -1"]
        stdout: StdioCollector {
            onStreamFinished: {
                const dir = text.trim();
                if (dir !== "") osd.backlight = dir;
            }
        }
    }

    FileView {
        path: osd.backlight === "" ? "" : osd.backlight + "max_brightness"
        onLoaded: osd.backlightMax = parseInt(text().trim()) || 0
    }

    FileView {
        path: osd.backlight === "" ? "" : osd.backlight + "brightness"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            if (osd.backlightMax <= 0) return;
            osd.flash("󰃠", "Brightness", parseInt(text().trim()) / osd.backlightMax);
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.panel
        border.color: Theme.border
        border.width: 1
        radius: 10

        Text {
            id: glyph
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            text: osd.icon
            color: Theme.accent
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize + 8
        }

        Text {
            id: name
            anchors.left: glyph.right
            anchors.leftMargin: 14
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.top: parent.top
            anchors.topMargin: 14
            text: osd.label + (osd.showValue ? "  " + Math.round(osd.value * 100) + "%" : "")
            color: Theme.fg
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize
        }

        Rectangle {
            id: track
            visible: osd.showValue
            anchors.left: name.left
            anchors.right: name.right
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 18
            height: 6
            radius: 3
            color: Theme.border

            Rectangle {
                width: track.width * Math.max(0, Math.min(1, osd.value))
                height: parent.height
                radius: 3
                color: Theme.accent
            }
        }
    }
}
