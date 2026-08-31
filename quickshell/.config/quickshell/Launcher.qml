import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Widgets
import QtQuick

// App launcher, clipboard picker and calculator — replaces walker + elephant
// and the `cliphist | rofi` bind. Opened over IPC from hyprland.lua:
//   qs ipc call launcher toggle      (apps; `=` calculates, `>` runs a command)
//   qs ipc call launcher clipboard   (cliphist history)
PanelWindow {
    id: launcher

    property string mode: "apps"
    property var clips: []
    property int selected: 0

    // Launch counts, so the apps you actually use sort first.
    property var frecency: ({})

    readonly property string query: input.text
    readonly property string prefix: mode === "apps" ? query.slice(0, 1) : ""
    readonly property string term: prefix === "=" || prefix === ">" ? query.slice(1).trim() : query

    readonly property var results: {
        if (mode === "clipboard") return filter(launcher.clips, c => c.text);
        if (prefix === "=") return calc(term);
        if (prefix === ">") return term === "" ? [] : [{ kind: "run", text: term, sub: "run command" }];
        return filter(DesktopEntries.applications.values.filter(a => !a.noDisplay), a => a.name);
    }

    // Subsequence match, ranked: exact prefix beats word start beats scattered.
    // Frecency breaks ties, which is the whole difference between this and an
    // alphabetical list.
    function filter(items, label) {
        const q = term.toLowerCase().trim();
        const scored = [];

        for (const item of items) {
            const name = (label(item) ?? "").toString();
            const hay = name.toLowerCase();
            let score = 0;

            if (q === "") {
                score = 1;
            } else if (hay.startsWith(q)) {
                score = 1000;
            } else if (hay.includes(" " + q) || hay.includes("-" + q)) {
                score = 500;
            } else if (hay.includes(q)) {
                score = 250;
            } else {
                // Scattered subsequence — last resort, and only in order.
                let i = 0;
                for (const ch of hay) if (ch === q[i]) i++;
                if (i < q.length) continue;
                score = 50;
            }

            score += Math.min(200, (launcher.frecency[name] ?? 0) * 20);
            score -= Math.min(40, name.length);
            scored.push({ item: item, name: name, score: score });
        }

        scored.sort((a, b) => b.score - a.score);
        return scored.slice(0, 30).map(s => launcher.mode === "clipboard"
            ? { kind: "clip", text: s.item.text, sub: "clipboard", clip: s.item }
            : { kind: "app", text: s.name, sub: s.item.genericName ?? s.item.comment ?? "", entry: s.item });
    }

    // Arithmetic only — anything else is not a sum and gets no result.
    function calc(expr) {
        if (expr === "" || !/^[0-9+\-*/(). %]+$/.test(expr)) return [];
        try {
            const value = Function("return (" + expr + ")")();
            if (typeof value !== "number" || !isFinite(value)) return [];
            return [{ kind: "calc", text: String(value), sub: expr + " — enter copies" }];
        } catch (e) {
            return [];
        }
    }

    function open(newMode) {
        launcher.mode = newMode;
        input.text = "";
        launcher.selected = 0;
        if (newMode === "clipboard") clipProc.running = true;
        launcher.visible = true;
        input.forceActiveFocus();
    }

    function close() {
        launcher.visible = false;
        input.text = "";
    }

    function activate() {
        const r = launcher.results[launcher.selected];
        if (!r) return;

        if (r.kind === "app") {
            launcher.frecency[r.text] = (launcher.frecency[r.text] ?? 0) + 1;
            frecencyFile.setText(JSON.stringify(launcher.frecency));
            r.entry.execute();
        } else if (r.kind === "run") {
            runProc.exec(["sh", "-c", r.text]);
        } else if (r.kind === "calc") {
            copyProc.exec(["sh", "-c", "printf %s " + JSON.stringify(r.text) + " | wl-copy"]);
        } else if (r.kind === "clip") {
            copyProc.exec(["sh", "-c", "cliphist decode " + JSON.stringify(r.clip.id) + " | wl-copy"]);
        }

        launcher.close();
    }

    IpcHandler {
        target: "launcher"

        function toggle(): void {
            if (launcher.visible && launcher.mode === "apps") launcher.close();
            else launcher.open("apps");
        }

        function clipboard(): void {
            if (launcher.visible && launcher.mode === "clipboard") launcher.close();
            else launcher.open("clipboard");
        }
    }

    FileView {
        id: frecencyFile
        // env() returns null when unset, so test truthiness, not "".
        path: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/quickshell-launcher.json"
        printErrors: false
        onLoaded: {
            try {
                launcher.frecency = JSON.parse(text());
            } catch (e) {
                launcher.frecency = ({});
            }
        }
    }

    Process {
        id: clipProc
        command: ["cliphist", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                // cliphist emits "<id>\t<preview>".
                launcher.clips = text.split("\n").filter(l => l !== "").map(line => {
                    const tab = line.indexOf("\t");
                    return { id: line.slice(0, tab), text: line.slice(tab + 1) };
                });
            }
        }
    }

    Process { id: runProc }
    Process { id: copyProc }

    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    WlrLayershell.namespace: "quickshell-launcher"

    anchors.top: true
    anchors.bottom: true
    anchors.left: true
    anchors.right: true
    exclusiveZone: 0
    color: "transparent"
    visible: false

    // Dim the desktop, and let a click anywhere out here dismiss.
    Rectangle {
        anchors.fill: parent
        color: "#99000000"

        MouseArea {
            anchors.fill: parent
            onClicked: launcher.close()
        }
    }

    Rectangle {
        id: box
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: parent.height * 0.18
        width: 640

        // Input (18 top margin + 28) + 14 gap + 1 rule, then the list's own
        // 8px margins top and bottom. Guessing this number clips the last row.
        readonly property int headerHeight: 18 + 28 + 14 + 1
        readonly property int listPadding: 16

        height: Math.min(520, headerHeight + listPadding + list.contentHeight)
        color: Theme.panel
        border.color: Theme.border
        border.width: 1
        radius: 10

        TextInput {
            id: input
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 18
            height: 28
            color: Theme.fg
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize + 3
            selectionColor: Theme.accent
            clip: true

            onTextChanged: launcher.selected = 0

            Text {
                anchors.fill: parent
                visible: input.text === ""
                text: launcher.mode === "clipboard" ? "Clipboard history…" : "Search apps…   = calc   > run"
                color: Theme.muted
                font: input.font
            }

            Keys.onEscapePressed: launcher.close()
            Keys.onReturnPressed: launcher.activate()
            Keys.onEnterPressed: launcher.activate()
            Keys.onDownPressed: launcher.selected = Math.min(launcher.selected + 1, launcher.results.length - 1)
            Keys.onUpPressed: launcher.selected = Math.max(launcher.selected - 1, 0)

            Keys.onPressed: event => {
                // Ctrl-n/p, because the hands are already there.
                if (event.modifiers & Qt.ControlModifier) {
                    if (event.key === Qt.Key_N) {
                        launcher.selected = Math.min(launcher.selected + 1, launcher.results.length - 1);
                        event.accepted = true;
                    } else if (event.key === Qt.Key_P) {
                        launcher.selected = Math.max(launcher.selected - 1, 0);
                        event.accepted = true;
                    }
                }
            }
        }

        Rectangle {
            id: rule
            anchors.top: input.bottom
            anchors.topMargin: 14
            width: parent.width
            height: 1
            color: Theme.border
        }

        ListView {
            id: list
            anchors.top: rule.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 8
            clip: true
            model: launcher.results
            currentIndex: launcher.selected
            highlightMoveDuration: 0
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)

            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index

                width: ListView.view.width
                height: 44
                radius: 6
                color: row.index === launcher.selected ? Theme.bg : "transparent"

                IconImage {
                    id: rowIcon
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    width: 24
                    height: 24
                    visible: row.modelData.kind === "app"
                    source: row.modelData.entry ? Quickshell.iconPath(row.modelData.entry.icon, true) : ""
                }

                Column {
                    anchors.left: rowIcon.visible ? rowIcon.right : parent.left
                    anchors.leftMargin: 10
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1

                    Text {
                        width: parent.width
                        text: row.modelData.text
                        color: Theme.fg
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: row.modelData.sub ?? ""
                        color: Theme.muted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize - 3
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        launcher.selected = row.index;
                        launcher.activate();
                    }
                }
            }
        }
    }
}
