import Quickshell.Io
import ".."

// systemd-inhibit holds the lock for as long as its child lives, so the running
// Process *is* the inhibit — killing it releases. hypridle honours the logind
// lock, so this suppresses both the idle timer and the lock.
BarItem {
    id: root
    property bool active: false

    text: active ? "󰈈" : "󰈉"
    color: active ? Theme.red : Theme.muted
    clickable: true
    onClicked: active = !active

    Process {
        running: root.active
        command: ["systemd-inhibit", "--what=idle", "--who=quickshell",
                  "--why=Manual idle inhibit", "sleep", "infinity"]
    }
}
