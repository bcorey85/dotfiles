import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts
import ".."

// CPU / RAM / temperature straight from /proc and /sys — no subprocess per tick,
// unlike waybar's custom-module pattern.
RowLayout {
    id: root
    spacing: 0

    property int cpuPct: 0
    property int memPct: 0
    property int tempC: -1

    // /proc/stat is cumulative; usage is the delta between samples.
    property double lastIdle: 0
    property double lastTotal: 0

    // The machine that has no thermal_zone0 (waybar disabled its module here)
    // still has hwmon; an empty path just leaves the module hidden.
    property string tempPath: ""

    FileView {
        id: statFile
        path: "/proc/stat"
        onLoaded: {
            const line = text().split("\n")[0].split(/\s+/).slice(1).map(Number);
            if (line.length < 4) return;
            const idle = line[3] + (line[4] ?? 0);
            const total = line.reduce((a, b) => a + b, 0);
            const dTotal = total - root.lastTotal;
            const dIdle = idle - root.lastIdle;
            if (root.lastTotal > 0 && dTotal > 0)
                root.cpuPct = Math.round(100 * (dTotal - dIdle) / dTotal);
            root.lastIdle = idle;
            root.lastTotal = total;
        }
    }

    FileView {
        id: memFile
        path: "/proc/meminfo"
        onLoaded: {
            const t = text();
            const total = Number(/MemTotal:\s+(\d+)/.exec(t)?.[1] ?? 0);
            const avail = Number(/MemAvailable:\s+(\d+)/.exec(t)?.[1] ?? 0);
            if (total > 0) root.memPct = Math.round(100 * (total - avail) / total);
        }
    }

    FileView {
        id: tempFile
        path: root.tempPath
        onLoaded: root.tempC = Math.round(Number(text().trim()) / 1000)
    }

    // One-shot probe for a usable temperature source.
    Process {
        running: true
        command: ["sh", "-c",
            "for f in /sys/class/thermal/thermal_zone*/temp /sys/class/hwmon/hwmon*/temp1_input; do " +
            "[ -r \"$f\" ] && { echo \"$f\"; exit 0; }; done"]
        stdout: StdioCollector {
            onStreamFinished: root.tempPath = text.trim()
        }
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            statFile.reload();
            memFile.reload();
            if (root.tempPath) tempFile.reload();
        }
    }

    BarItem {
        text: "  CPU " + root.cpuPct + "%"
        color: Theme.green
    }

    BarItem {
        text: "  RAM " + root.memPct + "%"
        color: Theme.red
    }

    BarItem {
        text: root.tempC < 0 ? "" : " " + root.tempC + "°C"
        color: root.tempC >= 80 ? Theme.red : Theme.orange
    }
}
