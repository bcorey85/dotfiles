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
        "gruvbox-material-dark": {
            bg: "#1d2021", panel: "#282828", border: "#3c3836",
            fg: "#e2cca9", muted: "#928374",
            green: "#b0b846", red: "#f2594b", teal: "#8bba7f",
            orange: "#f28534", yellow: "#e9b143", magenta: "#d3869b"
        },
        "gruvbox-material-light": {
            bg: "#f9f5d7", panel: "#f5edca", border: "#ebdbb2",
            fg: "#514036", muted: "#928374",
            green: "#72761e", red: "#af2528", teal: "#477a5b",
            orange: "#b94c07", yellow: "#b4730e", magenta: "#924f79"
        },
        "solarized-osaka-dark": {
            bg: "#001419", panel: "#000c10", border: "#063540",
            fg: "#839395", muted: "#586e74",
            green: "#849900", red: "#db302d", teal: "#29a298",
            orange: "#ca4c16", yellow: "#b28500", magenta: "#d23681"
        },
        "solarized-osaka-light": {
            bg: "#fdf5e2", panel: "#ede7d3", border: "#d8d0b6",
            fg: "#576d74", muted: "#647a82",
            green: "#6f8000", red: "#b7221f", teal: "#238682",
            orange: "#a23c11", yellow: "#8f6b00", magenta: "#b02769"
        },
        "solarized-dark": {
            bg: "#002b36", panel: "#073642", border: "#586e75",
            fg: "#839496", muted: "#586e75",
            green: "#859900", red: "#dc322f", teal: "#2aa198",
            orange: "#cb4b16", yellow: "#b58900", magenta: "#d33682"
        },
        "solarized-light": {
            bg: "#fdf6e3", panel: "#eee8d5", border: "#93a1a1",
            fg: "#657b83", muted: "#839496",
            green: "#859900", red: "#dc322f", teal: "#2aa198",
            orange: "#cb4b16", yellow: "#b58900", magenta: "#d33682"
        },
        "selenized-dark": {
            bg: "#103c48", panel: "#184956", border: "#2d5b69",
            fg: "#adbcbc", muted: "#72898f",
            green: "#75b938", red: "#fa5750", teal: "#41c7b9",
            orange: "#ed8649", yellow: "#dbb32d", magenta: "#f275be"
        },
        "selenized-light": {
            bg: "#fbf3db", panel: "#ece3cc", border: "#cfcebe",
            fg: "#53676d", muted: "#909995",
            green: "#489100", red: "#d2212d", teal: "#009c8f",
            orange: "#c25d1e", yellow: "#ad8900", magenta: "#ca4898"
        },
        "flexoki-dark": {
            bg: "#100f0f", panel: "#1c1b1a", border: "#343331",
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
        "alabaster-dark": {
            bg: "#0e1415", panel: "#162022", border: "#2b3d40",
            fg: "#cecece", muted: "#7d7d7d",
            green: "#95cb82", red: "#d2322d", teal: "#47bea9",
            orange: "#ec8013", yellow: "#cd974b", magenta: "#cc8bc9"
        },
        "alabaster-light": {
            bg: "#f7f7f7", panel: "#e7e7e7", border: "#c9c9c9",
            fg: "#000000", muted: "#696969",
            green: "#448c27", red: "#aa3731", teal: "#0083b2",
            orange: "#9a5c00", yellow: "#876004", magenta: "#7a3e9d"
        },
        "catppuccin-dark": {
            bg: "#1e1e2e", panel: "#181825", border: "#313244",
            fg: "#cdd6f4", muted: "#7f849c",
            green: "#a6e3a1", red: "#f38ba8", teal: "#94e2d5",
            orange: "#fab387", yellow: "#f9e2af", magenta: "#cba6f7"
        },
        "catppuccin-light": {
            bg: "#eff1f5", panel: "#e6e9ef", border: "#ccd0da",
            fg: "#4c4f69", muted: "#8c8fa1",
            green: "#40a02b", red: "#d20f39", teal: "#179299",
            orange: "#fe640b", yellow: "#df8e1d", magenta: "#8839ef"
        },
        "tokyonight-dark": {
            bg: "#1a1b26", panel: "#16161e", border: "#3b4261",
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
            bg: "#061a21", panel: "#01131a", border: "#2a3e47",
            fg: "#a0adb4", muted: "#9b9fa6",
            green: "#849900", red: "#de4f46", teal: "#29a298",
            orange: "#d66e31", yellow: "#bf983f", magenta: "#e34990"
        },
        "dredge-light": {
            bg: "#c8d0d3", panel: "#c2cacd", border: "#a5adb0",
            fg: "#293741", muted: "#4e5158",
            green: "#4f5d00", red: "#a32822", teal: "#00625c",
            orange: "#943b12", yellow: "#6d4a00", magenta: "#a80e62"
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
    // Families that differ only in nvim syntax borrow another family's palette (theme-mode asset_family).
    readonly property var aliases: ({ "dredge-roles": "dredge" })
    readonly property string paletteFamily: aliases[family] ?? family
    readonly property var p: palettes[paletteFamily + "-" + mode] ?? palettes["onedarkpro-" + mode] ?? palettes["onedarkpro-dark"]

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
