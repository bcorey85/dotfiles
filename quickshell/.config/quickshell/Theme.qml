pragma Singleton

// The reason this package exists: waybar/rofi/dunst/hyprlock are dark-only with
// hardcoded hex. This follows the same two state files everything else reads
// (~/.cache/theme-family, ~/.cache/theme-mode) and repaints live, no reload.
import Quickshell
import Quickshell.Io
import QtQuick

Singleton {
    id: root

    property string family: "dredge"
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
        "dredge-dark": {
            bg: "#1c1c1c", panel: "#161616", border: "#454545",
            fg: "#c0c0c0", muted: "#a1a1a1",
            green: "#8d9f43", red: "#dc7f76", teal: "#51a49c",
            orange: "#d68356", yellow: "#af955f", magenta: "#d97d94"
        },
        "dredge-light": {
            bg: "#c8d0d3", panel: "#c2cacd", border: "#a5adb0",
            fg: "#1f2d37", muted: "#4e5158",
            green: "#445200", red: "#951816", teal: "#005751",
            orange: "#872f00", yellow: "#6d4a00", magenta: "#940053"
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
        "min-dark": {
            bg: "#181616", panel: "#0d0c0c", border: "#393836",
            fg: "#eeeada", muted: "#8e8c84",
            green: "#98bb6c", red: "#e46876", teal: "#7aa89f",
            orange: "#ffa066", yellow: "#e6c384", magenta: "#957fb8"
        },
        "min-light": {
            bg: "#f2ecbc", panel: "#e5ddb0", border: "#d5cea3",
            fg: "#2e2e3d", muted: "#636262",
            green: "#6f894e", red: "#c84053", teal: "#597b75",
            orange: "#cc6d00", yellow: "#836f4a", magenta: "#766b90"
        },
        "kanagawa-paper-dark": {
            bg: "#1f1f28", panel: "#16161d", border: "#363646",
            fg: "#dcd7ba", muted: "#9e9b93",
            green: "#8a9a7b", red: "#c4746e", teal: "#8ea49e",
            orange: "#b6927b", yellow: "#c4b28a", magenta: "#a292a3"
        },
        "kanagawa-paper-light": {
            bg: "#e1e1de", panel: "#d8d8d2", border: "#cbc8bc",
            fg: "#616569", muted: "#77746c",
            green: "#6a7d66", red: "#a36360", teal: "#5c8388",
            orange: "#a1805e", yellow: "#91825e", magenta: "#947992"
        },
        "monoglow-dark": {
            bg: "#1c1c1c", panel: "#212121", border: "#404040",
            fg: "#c0c0c0", muted: "#a1a1a1",
            green: "#b3f6c0", red: "#ffc0b9", teal: "#33e6c6",
            orange: "#fce094", yellow: "#fce094", magenta: "#ffcaff"
        },
        "monoglow-light": {
            bg: "#f0f0f0", panel: "#ebebeb", border: "#b0b0b0",
            fg: "#3a3a3a", muted: "#707070",
            green: "#2a7a40", red: "#c04040", teal: "#2e8a8a",
            orange: "#9a7a20", yellow: "#9a7a20", magenta: "#8a3a8a"
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

    // Unknown family falls back to dredge rather than leaving the bar unpainted.
    readonly property var p: palettes[family + "-" + mode] ?? palettes["dredge-" + mode] ?? palettes["dredge-dark"]

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
