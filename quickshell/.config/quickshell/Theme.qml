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
        // wave / lotus — the one family whose two modes are separate
        // colorschemes upstream; here they are just two palettes like the rest.
        "kanagawa-dark": {
            bg: "#1f1f28", panel: "#2a2a37", border: "#363646",
            fg: "#dcd7ba", muted: "#908f85",
            green: "#98bb6c", red: "#e46876", teal: "#7aa89f",
            orange: "#ffa066", yellow: "#e6c384", magenta: "#957fb8"
        },
        "kanagawa-light": {
            bg: "#f2ecbc", panel: "#e5ddb0", border: "#d5cea3",
            fg: "#545464", muted: "#6a6a5e",
            green: "#6e915f", red: "#c84053", teal: "#597b75",
            orange: "#cc6d00", yellow: "#836f4a", magenta: "#b35b79"
        },
        // forest / field. thorn has no magenta, so its peach stands in.
        "thorn-dark": {
            bg: "#172526", panel: "#131f20", border: "#233935",
            fg: "#dbd2c7", muted: "#9b9a8c",
            green: "#94c68b", red: "#d2696c", teal: "#87cbb1",
            orange: "#f2a597", yellow: "#ffd7aa", magenta: "#f2a597"
        },
        // field's authored hues are 2.5-4:1 on its cream; darkened per hue.
        "thorn-light": {
            bg: "#f9fdce", panel: "#eff5bd", border: "#cfd69e",
            fg: "#3d4a2b", muted: "#74694e",
            green: "#516f21", red: "#b0453f", teal: "#2a7342",
            orange: "#a04b28", yellow: "#8a6a1e", magenta: "#a04b28"
        },
        // darkest dark variant / warmest light variant; light hues darkened
        // to clear 4.5:1 on parchment.
        "ember-dark": {
            bg: "#1c1b19", panel: "#252422", border: "#3e3c38",
            fg: "#d8d0c0", muted: "#908a7e",
            green: "#8a9868", red: "#b07878", teal: "#80a090",
            orange: "#e08060", yellow: "#c8b468", magenta: "#988090"
        },
        "ember-light": {
            bg: "#e6dac4", panel: "#d8ccb0", border: "#b8ac96",
            fg: "#282418", muted: "#605848",
            green: "#4a6830", red: "#874a4a", teal: "#386858",
            orange: "#a44024", yellow: "#6b5a18", magenta: "#665766"
        },
        "material-dark": {
            bg: "#212121", panel: "#323232", border: "#343434",
            fg: "#B0BEC5", muted: "#848b93",
            green: "#C3E88D", red: "#F07178", teal: "#89DDFF",
            orange: "#F78C6C", yellow: "#FFCB6B", magenta: "#C792EA"
        },
        "material-light": {
            bg: "#FAFAFA", panel: "#E7E7E8", border: "#D3E1E8",
            fg: "#546E7A", muted: "#5d6d77",
            green: "#4e6f1f", red: "#B20602", teal: "#056a72",
            orange: "#b23a12", yellow: "#8a5a00", magenta: "#7C4DFF"
        },
        "github-dark": {
            bg: "#30363d", panel: "#363c44", border: "#484f58",
            fg: "#e6edf3", muted: "#9aa4ae",
            green: "#3fb950", red: "#ff7b72", teal: "#76e3ea",
            orange: "#ffa657", yellow: "#d29922", magenta: "#bc8cff"
        },
        "github-light": {
            bg: "#ffffff", panel: "#e7eaf0", border: "#d0d7de",
            fg: "#1f2328", muted: "#57606a",
            green: "#1a7f37", red: "#d1242f", teal: "#1b7f8b",
            orange: "#bc4c00", yellow: "#9a6700", magenta: "#8250df"
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
        "oceanic-dark": {
            bg: "#25363B", panel: "#314549", border: "#355058",
            fg: "#B0BEC5", muted: "#93a3ae",
            green: "#C3E88D", red: "#f47f88", teal: "#89DDFF",
            orange: "#F78C6C", yellow: "#FFCB6B", magenta: "#C792EA"
        },
        "oceanic-light": {
            bg: "#FAFAFA", panel: "#E7E7E8", border: "#D3E1E8",
            fg: "#546E7A", muted: "#5d6d77",
            green: "#4e6f1f", red: "#B20602", teal: "#056a72",
            orange: "#b23a12", yellow: "#8a5a00", magenta: "#7C4DFF"
        },
        "catppuccin-dark": {
            bg: "#303446", panel: "#292c3c", border: "#51576d",
            fg: "#c6d0f5", muted: "#949cbb",
            green: "#a6d189", red: "#e78284", teal: "#81c8be",
            orange: "#ef9f76", yellow: "#e5c890", magenta: "#ca9ee6"
        },
        "catppuccin-light": {
            bg: "#eff1f5", panel: "#e6e9ef", border: "#bcc0cc",
            fg: "#4c4f69", muted: "#6c6f85",
            green: "#2f7a1f", red: "#d20f39", teal: "#10727a",
            orange: "#b84700", yellow: "#9a6200", magenta: "#8839ef"
        },
        "tokyonight-dark": {
            bg: "#24283b", panel: "#1f2335", border: "#3b4261",
            fg: "#c0caf5", muted: "#8289a8",
            green: "#9ece6a", red: "#f7768e", teal: "#1abc9c",
            orange: "#ff9e64", yellow: "#e0af68", magenta: "#bb9af7"
        },
        "tokyonight-light": {
            bg: "#e1e2e7", panel: "#d0d5e3", border: "#a8aecb",
            fg: "#3760bf", muted: "#565b76",
            green: "#4b6330", red: "#b01e49", teal: "#0d6957",
            orange: "#8f4b00", yellow: "#715732", magenta: "#7440b7"
        },
        "rose-pine-dark": {
            bg: "#232136", panel: "#2a273f", border: "#44415a",
            fg: "#e0def4", muted: "#918dab",
            green: "#4f99b7", red: "#eb6f92", teal: "#ea9a97",
            orange: "#ea9a97", yellow: "#f6c177", magenta: "#c4a7e7"
        },
        "rose-pine-light": {
            bg: "#faf4ed", panel: "#f2e9e1", border: "#cecacd",
            fg: "#575279", muted: "#6a6781",
            green: "#286983", red: "#995468", teal: "#945a57",
            orange: "#945a57", yellow: "#8f6020", magenta: "#736287"
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
