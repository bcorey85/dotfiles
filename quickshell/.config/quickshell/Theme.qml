pragma Singleton

// The reason this package exists: waybar/rofi/dunst/hyprlock are dark-only with
// hardcoded hex. This follows the same two state files everything else reads
// (~/.cache/theme-family, ~/.cache/theme-mode) and repaints live, no reload.
import Quickshell
import Quickshell.Io
import QtQuick

Singleton {
    id: root

    property string family: "vitesse"
    property string mode: "dark"

    readonly property var palettes: ({
        "vitesse-dark": {
            bg: "#121212", panel: "#181818", border: "#393939",
            fg: "#c8c5b8", muted: "#83827d",
            green: "#4d9375", red: "#cb7676", teal: "#5eaab5",
            orange: "#d4976c", yellow: "#e6cc77", magenta: "#d9739f"
        },
        "vitesse-light": {
            bg: "#ffffff", panel: "#f2f2f2", border: "#d8d8d8",
            fg: "#393a34", muted: "#6b7a6b",
            green: "#1e754f", red: "#ab5959", teal: "#2993a3",
            orange: "#a65e2b", yellow: "#bda437", magenta: "#b56398"
        },
        "flexoki-dark": {
            bg: "#100f0f", panel: "#1c1b1a", border: "#403e3c",
            fg: "#cecdc3", muted: "#878580",
            green: "#879a39", red: "#d14d41", teal: "#3aa99f",
            orange: "#da702c", yellow: "#d0a215", magenta: "#ce5d97"
        },
        "flexoki-light": {
            bg: "#fffcf0", panel: "#f2f0e5", border: "#dad8ce",
            fg: "#100f0f", muted: "#6f6e69",
            green: "#66800b", red: "#af3029", teal: "#24837b",
            orange: "#bc5215", yellow: "#ad8301", magenta: "#a02f6f"
        },
        "bamboo-dark": {
            bg: "#252623", panel: "#2f312c", border: "#454842",
            fg: "#f1e9d2", muted: "#8e938c",
            green: "#8fb573", red: "#e75a7c", teal: "#70c2be",
            orange: "#ff9966", yellow: "#dbb651", magenta: "#aaaaff"
        },
        "bamboo-light": {
            bg: "#fafae0", panel: "#eaead0", border: "#d0d0b8",
            fg: "#3a4238", muted: "#66695f",
            green: "#27850b", red: "#c72a3c", teal: "#188a9e",
            orange: "#df5926", yellow: "#a77b00", magenta: "#8a4adf"
        },
        "gruvbox-dark": {
            bg: "#282828", panel: "#3c3836", border: "#665c54",
            fg: "#ebdbb2", muted: "#9e8d7d",
            green: "#b8bb26", red: "#fb4934", teal: "#8ec07c",
            orange: "#fe8019", yellow: "#fabd2f", magenta: "#d3869b"
        },
        "gruvbox-light": {
            bg: "#fbf1c7", panel: "#ebdbb2", border: "#bdae93",
            fg: "#3c3836", muted: "#776a5e",
            green: "#79740e", red: "#9d0006", teal: "#427b58",
            orange: "#af3a03", yellow: "#b57614", magenta: "#8f3f71"
        },
        "melange-dark": {
            bg: "#292522", panel: "#34302c", border: "#4a443f",
            fg: "#ece1d7", muted: "#c1a78e",
            green: "#85b695", red: "#d47766", teal: "#7b9695",
            orange: "#e49b5d", yellow: "#ebc06d", magenta: "#cf9bc2"
        },
        "melange-light": {
            bg: "#f1f1f1", panel: "#e9e1db", border: "#cfc7bf",
            fg: "#54433a", muted: "#7d6658",
            green: "#6e9b72", red: "#bf0021", teal: "#739797",
            orange: "#bc5c00", yellow: "#a06d00", magenta: "#904180"
        },
        // dragon / lotus — the one family whose two modes are separate
        // colorschemes upstream; here they are just two palettes like the rest.
        "kanagawa-dark": {
            bg: "#181616", panel: "#1d1c19", border: "#393836",
            fg: "#c5c9c5", muted: "#838a82",
            green: "#87a987", red: "#c4746e", teal: "#8ea4a2",
            orange: "#b6927b", yellow: "#c4b28a", magenta: "#a292a3"
        },
        "kanagawa-light": {
            bg: "#f2ecbc", panel: "#e5ddb0", border: "#d5cea3",
            fg: "#545464", muted: "#6a6a5e",
            green: "#6e915f", red: "#c84053", teal: "#597b75",
            orange: "#cc6d00", yellow: "#836f4a", magenta: "#b35b79"
        }
    })

    // Unknown family falls back to vitesse rather than leaving the bar unpainted.
    readonly property var p: palettes[family + "-" + mode] ?? palettes["vitesse-" + mode] ?? palettes["vitesse-dark"]

    readonly property color bg: p.bg
    readonly property color panel: p.panel
    readonly property color border: p.border
    readonly property color fg: p.fg
    readonly property color muted: p.muted
    readonly property color green: p.green
    readonly property color red: p.red
    readonly property color teal: p.teal
    readonly property color orange: p.orange
    readonly property color yellow: p.yellow
    readonly property color magenta: p.magenta

    readonly property color accent: teal

    readonly property string fontFamily: "FiraCode Nerd Font Mono"
    readonly property int fontSize: 13
    readonly property int barHeight: 36

    FileView {
        path: Quickshell.env("HOME") + "/.cache/theme-family"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            const v = text().trim();
            if (v) root.family = v;
        }
    }

    FileView {
        path: Quickshell.env("HOME") + "/.cache/theme-mode"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            const v = text().trim();
            if (v) root.mode = v;
        }
    }
}
