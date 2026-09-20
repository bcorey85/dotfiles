pragma Singleton

// The reason this package exists: waybar/rofi/dunst/hyprlock are dark-only with
// hardcoded hex. This follows the same two state files everything else reads
// (~/.cache/theme-family, ~/.cache/theme-mode) and repaints live, no reload.
import Quickshell
import Quickshell.Io
import QtQuick

Singleton {
    id: root

    property string family: "flexoki"
    property string mode: "dark"

    readonly property var palettes: ({
        "flexoki-dark": {
            bg: "#100f0f", panel: "#1c1b1a", border: "#403e3c",
            fg: "#cecdc3", muted: "#575653",
            green: "#879a39", red: "#d14d41", teal: "#3aa99f",
            orange: "#da702c", yellow: "#d0a215", magenta: "#ce5d97"
        },
        "flexoki-light": {
            bg: "#fffcf0", panel: "#f2f0e5", border: "#dad8ce",
            fg: "#100f0f", muted: "#b7b5ac",
            green: "#66800b", red: "#af3029", teal: "#24837b",
            orange: "#bc5215", yellow: "#ad8301", magenta: "#a02f6f"
        },
        "bamboo-dark": {
            bg: "#252623", panel: "#2f312c", border: "#454842",
            fg: "#f1e9d2", muted: "#838781",
            green: "#8fb573", red: "#e75a7c", teal: "#70c2be",
            orange: "#ff9966", yellow: "#dbb651", magenta: "#aaaaff"
        },
        "bamboo-light": {
            bg: "#fafae0", panel: "#eaead0", border: "#d0d0b8",
            fg: "#3a4238", muted: "#838781",
            green: "#27850b", red: "#c72a3c", teal: "#188a9e",
            orange: "#df5926", yellow: "#a77b00", magenta: "#8a4adf"
        },
        "tokyonight-dark": {
            bg: "#24283b", panel: "#1f2335", border: "#3b4261",
            fg: "#c0caf5", muted: "#565f89",
            green: "#9ece6a", red: "#f7768e", teal: "#1abc9c",
            orange: "#ff9e64", yellow: "#e0af68", magenta: "#bb9af7"
        },
        "tokyonight-light": {
            bg: "#e1e2e7", panel: "#d0d5e3", border: "#a8aecb",
            fg: "#3760bf", muted: "#848cb5",
            green: "#587539", red: "#f52a65", teal: "#118c74",
            orange: "#b15c00", yellow: "#8c6c3e", magenta: "#9854f1"
        },
        "onedark-dark": {
            bg: "#282c34", panel: "#31353f", border: "#3b3f4c",
            fg: "#abb2bf", muted: "#5c6370",
            green: "#98c379", red: "#e86671", teal: "#56b6c2",
            orange: "#d19a66", yellow: "#e5c07b", magenta: "#c678dd"
        },
        "onedark-light": {
            bg: "#fafafa", panel: "#f0f0f0", border: "#dcdcdc",
            fg: "#383a42", muted: "#a0a1a7",
            green: "#50a14f", red: "#e45649", teal: "#0184bc",
            orange: "#c18401", yellow: "#986801", magenta: "#a626a4"
        },
        "dracula-dark": {
            bg: "#282A36", panel: "#21222C", border: "#44475A",
            fg: "#F8F8F2", muted: "#6272A4",
            green: "#50FA7B", red: "#FF5555", teal: "#8BE9FD",
            orange: "#FFB86C", yellow: "#F1FA8C", magenta: "#FF79C6"
        },
        "dracula-light": {
            bg: "#FFFBEB", panel: "#ECE9DF", border: "#CECCC0",
            fg: "#1F1F1F", muted: "#6C664B",
            green: "#14710A", red: "#CB3A2A", teal: "#036A96",
            orange: "#A34D14", yellow: "#846E15", magenta: "#A3144D"
        },
        "nightfox-dark": {
            bg: "#192330", panel: "#131a24", border: "#29394f",
            fg: "#cdcecf", muted: "#738091",
            green: "#81b29a", red: "#c94f6d", teal: "#63cdcf",
            orange: "#f4a261", yellow: "#dbc074", magenta: "#9d79d6"
        },
        "nightfox-light": {
            bg: "#f6f2ee", panel: "#e4dcd4", border: "#d3c7bb",
            fg: "#3d2b5a", muted: "#837a72",
            green: "#396847", red: "#a5222f", teal: "#287980",
            orange: "#955f61", yellow: "#AC5402", magenta: "#6e33ce"
        },
        "duskfox-dark": {
            bg: "#232136", panel: "#191726", border: "#373354",
            fg: "#e0def4", muted: "#817c9c",
            green: "#a3be8c", red: "#eb6f92", teal: "#9ccfd8",
            orange: "#ea9a97", yellow: "#f6c177", magenta: "#c4a7e7"
        },
        "duskfox-light": {
            bg: "#faf4ed", panel: "#ebe5df", border: "#ebdfe4",
            fg: "#575279", muted: "#9893a5",
            green: "#618774", red: "#b4637a", teal: "#56949f",
            orange: "#d7827e", yellow: "#ea9d34", magenta: "#907aa9"
        },
        "aura-dark": {
            bg: "#15141b", panel: "#1e1c28", border: "#3b3557",
            fg: "#bdbdbd", muted: "#8e8e8e",
            green: "#54c59f", red: "#c55858", teal: "#6cb2c7",
            orange: "#c7a06f", yellow: "#c7a06f", magenta: "#8464c6"
        },
        "aura-light": {
            bg: "#15141b", panel: "#1e1c28", border: "#3b3557",
            fg: "#bdbdbd", muted: "#8e8e8e",
            green: "#54c59f", red: "#c55858", teal: "#6cb2c7",
            orange: "#c7a06f", yellow: "#c7a06f", magenta: "#8464c6"
        }
    })

    // Unknown family falls back to flexoki rather than leaving the bar unpainted.
    readonly property var p: palettes[family + "-" + mode] ?? palettes["flexoki-" + mode] ?? palettes["flexoki-dark"]

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
