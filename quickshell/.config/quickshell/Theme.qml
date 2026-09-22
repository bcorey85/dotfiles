pragma Singleton

// The reason this package exists: waybar/rofi/dunst/hyprlock are dark-only with
// hardcoded hex. This follows the same two state files everything else reads
// (~/.cache/theme-family, ~/.cache/theme-mode) and repaints live, no reload.
import Quickshell
import Quickshell.Io
import QtQuick

Singleton {
    id: root

    property string family: "onedarkpro"
    property string mode: "dark"

    readonly property var palettes: ({
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
        "onedarkpro-dark": {
            bg: "#282c34", panel: "#21252b", border: "#3b4048",
            fg: "#abb2bf", muted: "#7f848e",
            green: "#98c379", red: "#e06c75", teal: "#56b6c2",
            orange: "#d19a66", yellow: "#e5c07b", magenta: "#c678dd"
        },
        "onedarkpro-light": {
            bg: "#fafafa", panel: "#efefef", border: "#e7e7e7",
            fg: "#6a6a6a", muted: "#9b9fa6",
            green: "#1da912", red: "#e05661", teal: "#56b6c2",
            orange: "#ee9025", yellow: "#eea825", magenta: "#9a77cf"
        },
        "edge-dark": {
            bg: "#2b2d37", panel: "#333644", border: "#454b60",
            fg: "#c5cdd9", muted: "#9199a9",
            green: "#a0c980", red: "#ec7279", teal: "#5dbbc1",
            orange: "#deb974", yellow: "#deb974", magenta: "#d38aea"
        },
        "edge-light": {
            bg: "#fafafa", panel: "#eef1f4", border: "#ccd3db",
            fg: "#4b505b", muted: "#677182",
            green: "#537a2b", red: "#c93f3f", teal: "#337b75",
            orange: "#9a6604", yellow: "#9a6604", magenta: "#a545c5"
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
        "dredge-dark": {
            bg: "#211f1c", panel: "#1b1917", border: "#413d39",
            fg: "#d1d1d1", muted: "#929292",
            green: "#82d395", red: "#f77972", teal: "#79cfcf",
            orange: "#ffa475", yellow: "#ebc75b", magenta: "#e091d8"
        },
        "dredge-light": {
            bg: "#efece8", panel: "#eae6e1", border: "#c5c1b9",
            fg: "#383838", muted: "#7b7a78",
            green: "#1d7d3e", red: "#ba3535", teal: "#007475",
            orange: "#bb5d00", yellow: "#9d7200", magenta: "#993f94"
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

    // Unknown family falls back to onedarkpro rather than leaving the bar unpainted.
    readonly property var p: palettes[family + "-" + mode] ?? palettes["onedarkpro-" + mode] ?? palettes["onedarkpro-dark"]

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
