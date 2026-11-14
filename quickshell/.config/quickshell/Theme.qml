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
        "token-flint-dark": {
            bg: "#272c33", panel: "#1c2127", border: "#373e47",
            fg: "#c3c8cc", muted: "#858f9b",
            green: "#a9b98c", red: "#e3888c", teal: "#98bbd4",
            orange: "#eb9e83", yellow: "#f8d28a", magenta: "#c59ab2"
        },
        "token-flint-light": {
            bg: "#f5f7f8", panel: "#e7ebef", border: "#d9dee3",
            fg: "#283039", muted: "#5a6571",
            green: "#3d5902", red: "#bf3f50", teal: "#09567b",
            orange: "#902a03", yellow: "#996914", magenta: "#7c4c5f"
        },
        "token-dark": {
            bg: "#262624", panel: "#1d1d1c", border: "#383835",
            fg: "#c3c0b8", muted: "#8a8884",
            green: "#8fb78c", red: "#d68585", teal: "#7dbbba",
            orange: "#f4906f", yellow: "#f7c699", magenta: "#c293a4"
        },
        "token-light": {
            bg: "#faf9f5", panel: "#ecebe7", border: "#e6e5e1",
            fg: "#323128", muted: "#6a655d",
            green: "#365a33", red: "#ad5253", teal: "#185b5b",
            orange: "#863716", yellow: "#857238", magenta: "#794f5f"
        },
        "jellybeans-dark": {
            bg: "#151515", panel: "#1c1c1c", border: "#404040",
            fg: "#e8e8d3", muted: "#888888",
            green: "#99ad6a", red: "#d74545", teal: "#8fbfdc",
            orange: "#d98870", yellow: "#fad07a", magenta: "#c6b6ee"
        },
        "jellybeans-light": {
            bg: "#f5e6d3", panel: "#e8d5c0", border: "#d8c8b8",
            fg: "#252525", muted: "#686868",
            green: "#386014", red: "#a02020", teal: "#2b5b77",
            orange: "#954d3b", yellow: "#876820", magenta: "#5f43aa"
        },
        "catppuccin-dark": {
            bg: "#303446", panel: "#292c3c", border: "#414559",
            fg: "#c6d0f5", muted: "#838ba7",
            green: "#a6d189", red: "#e78284", teal: "#81c8be",
            orange: "#ef9f76", yellow: "#e5c890", magenta: "#ca9ee6"
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
            bg: "#1b1f23", panel: "#14181b", border: "#43484b",
            fg: "#b7bbbd", muted: "#a5a9b0",
            green: "#8fa338", red: "#d46e65", teal: "#4baba2",
            orange: "#da7e4b", yellow: "#c7a459", magenta: "#d57299"
        },
        "dredge-light": {
            bg: "#c8d0d3", panel: "#c2cacd", border: "#a5adb0",
            fg: "#293741", muted: "#4e5158",
            green: "#4f5d00", red: "#a32822", teal: "#00625c",
            orange: "#943b12", yellow: "#6d4a00", magenta: "#a80e62"
        },
        "kanagawa-dark": {
            bg: "#1f1f28", panel: "#16161d", border: "#363646",
            fg: "#dcd7ba", muted: "#9b9989",
            green: "#98bb6c", red: "#e46876", teal: "#7aa89f",
            orange: "#ffa066", yellow: "#e6c384", magenta: "#957fb8"
        },
        "kanagawa-light": {
            bg: "#f2ecbc", panel: "#e5ddb0", border: "#d5cea3",
            fg: "#545464", muted: "#6d6a5d",
            green: "#587137", red: "#bf374c", teal: "#4e6f69",
            orange: "#ab4e00", yellow: "#716b39", magenta: "#a44e6c"
        },
        "darcula-dark": {
            bg: "#2b2b2b", panel: "#242424", border: "#484848",
            fg: "#c9d0d3", muted: "#929292",
            green: "#98be65", red: "#f43753", teal: "#73cef4",
            orange: "#dc9656", yellow: "#ffc66d", magenta: "#a785ba"
        },
        "darcula-light": {
            bg: "#2b2b2b", panel: "#242424", border: "#484848",
            fg: "#c9d0d3", muted: "#929292",
            green: "#98be65", red: "#f43753", teal: "#73cef4",
            orange: "#dc9656", yellow: "#ffc66d", magenta: "#a785ba"
        },
        "tairiki-dark": {
            bg: "#151515", panel: "#1d1f21", border: "#3b3f4c",
            fg: "#c5c8c6", muted: "#969896",
            green: "#b5bd68", red: "#cc6666", teal: "#7eada7",
            orange: "#de935f", yellow: "#f0c674", magenta: "#b294bb"
        },
        "tairiki-light": {
            bg: "#ffffff", panel: "#f0f0f8", border: "#d8d8d0",
            fg: "#001070", muted: "#595959",
            green: "#008000", red: "#a31515", teal: "#1e797f",
            orange: "#cf4a11", yellow: "#7c5c20", magenta: "#7929c8"
        },
        "everforest-dark": {
            bg: "#272e33", panel: "#1e2326", border: "#414b50",
            fg: "#d3c6aa", muted: "#9da9a0",
            green: "#a7c080", red: "#e67e80", teal: "#83c092",
            orange: "#e69875", yellow: "#dbbc7f", magenta: "#d699b6"
        },
        "everforest-light": {
            bg: "#fffbef", panel: "#f2efdf", border: "#e8e5d5",
            fg: "#5c6a72", muted: "#667565",
            green: "#677900", red: "#d43034", teal: "#008058",
            orange: "#bf4c00", yellow: "#a06400", magenta: "#b64394"
        },
        "gruvbox-dark": {
            bg: "#282828", panel: "#1d2021", border: "#504945",
            fg: "#ebdbb2", muted: "#928374",
            green: "#b8bb26", red: "#fb4934", teal: "#8ec07c",
            orange: "#fe8019", yellow: "#fabd2f", magenta: "#d3869b"
        },
        "gruvbox-light": {
            bg: "#fbf1c7", panel: "#f2e5bc", border: "#d5c4a1",
            fg: "#3c3836", muted: "#7c6f64",
            green: "#79740e", red: "#9d0006", teal: "#427b58",
            orange: "#af3a03", yellow: "#b57614", magenta: "#8f3f71"
        },
        "papercolor-dark": {
            bg: "#1c1c1c", panel: "#121212", border: "#3a3a3a",
            fg: "#d0d0d0", muted: "#949494",
            green: "#5faf00", red: "#ff5faf", teal: "#00afaf",
            orange: "#d7875f", yellow: "#d7af5f", magenta: "#af87d7"
        },
        "papercolor-light": {
            bg: "#eeeeee", panel: "#e4e4e4", border: "#d0d0d0",
            fg: "#444444", muted: "#626262",
            green: "#008700", red: "#af0000", teal: "#0087af",
            orange: "#d75f00", yellow: "#af5f00", magenta: "#8700af"
        },
        "hybrid-dark": {
            bg: "#1d1f21", panel: "#151718", border: "#373b41",
            fg: "#c5c8c6", muted: "#8b9299",
            green: "#b5bd68", red: "#cc6666", teal: "#8abeb7",
            orange: "#de935f", yellow: "#f0c674", magenta: "#b294bb"
        },
        "hybrid-light": {
            bg: "#ffffff", panel: "#efefef", border: "#d6d6d6",
            fg: "#4d4d4c", muted: "#70726e",
            green: "#5f7700", red: "#c82829", teal: "#2c7d83",
            orange: "#b85a00", yellow: "#8f6f00", magenta: "#8959a8"
        },
        "vitesse-dark": {
            bg: "#121212", panel: "#181818", border: "#2f2f2f",
            fg: "#cecabe", muted: "#858480",
            green: "#4d9375", red: "#cb7676", teal: "#5eaab5",
            orange: "#d4976c", yellow: "#e6cc77", magenta: "#d9739f"
        },
        "vitesse-light": {
            bg: "#ffffff", panel: "#f7f7f7", border: "#dedede",
            fg: "#393a34", muted: "#8f908c",
            green: "#1e754f", red: "#ab5959", teal: "#2993a3",
            orange: "#a65e2b", yellow: "#bda437", magenta: "#a13865"
        },
        "rose-pine-dark": {
            bg: "#191724", panel: "#1f1d2e", border: "#403d52",
            fg: "#e0def4", muted: "#908caa",
            green: "#31748f", red: "#eb6f92", teal: "#9ccfd8",
            orange: "#ebbcba", yellow: "#f6c177", magenta: "#c4a7e7"
        },
        "rose-pine-light": {
            bg: "#faf4ed", panel: "#fffaf3", border: "#dfdad9",
            fg: "#464261", muted: "#797593",
            green: "#286983", red: "#b4637a", teal: "#56949f",
            orange: "#d7827e", yellow: "#ea9d34", magenta: "#907aa9"
        },
        "ef-elea-dark": {
            bg: "#222524", panel: "#303332", border: "#5e6160",
            fg: "#eaf2ef", muted: "#969faf",
            green: "#7fc87f", red: "#ff656a", teal: "#6fcfd2",
            orange: "#e0b02f", yellow: "#cac85f", magenta: "#f59acf"
        },
        "ef-elea-light": {
            bg: "#edf5e2", panel: "#e3e9d6", border: "#b0b7aa",
            fg: "#221321", muted: "#676470",
            green: "#00601f", red: "#c3303a", teal: "#1f70af",
            orange: "#b04300", yellow: "#9a501f", magenta: "#80308f"
        },
        "ef-maris-dark": {
            bg: "#131c2b", panel: "#1d2c39", border: "#4a5664",
            fg: "#eaedef", muted: "#969faf",
            green: "#41bf4f", red: "#ff6f6f", teal: "#2fd0db",
            orange: "#f0c060", yellow: "#d0d24f", magenta: "#f59acf"
        },
        "ef-maris-light": {
            bg: "#edf4f8", panel: "#e0e7ef", border: "#afb8c3",
            fg: "#151a27", muted: "#676470",
            green: "#007010", red: "#c3303a", teal: "#1f66af",
            orange: "#8b4400", yellow: "#805a1f", magenta: "#80308f"
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
