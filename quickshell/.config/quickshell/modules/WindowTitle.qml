import Quickshell.Hyprland
import QtQuick
import ".."

// This build's Quickshell ships no wlr-foreign-toplevel binding (the Wayland
// module exports only WlSessionLock), so the title comes from Hyprland's own
// toplevel tracking. Guarded: an absent property leaves the label empty rather
// than erroring on every focus change.
Text {
    readonly property var activeTop: Hyprland.activeToplevel ?? null

    text: activeTop?.title ?? ""
    elide: Text.ElideRight
    maximumLineCount: 1
    color: Theme.muted
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontSize
    leftPadding: 12
}
