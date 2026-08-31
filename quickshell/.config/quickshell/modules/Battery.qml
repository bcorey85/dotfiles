import Quickshell.Services.UPower
import ".."

// Hidden on desktops — BarItem drops itself when text is empty, so this costs
// nothing on the machine with no battery.
BarItem {
    readonly property var dev: UPower.displayDevice
    readonly property bool present: dev?.isPresent ?? false
    readonly property int pct: Math.round(dev?.percentage ?? 0)
    readonly property bool charging: dev?.state === UPowerDeviceState.Charging

    text: !present ? "" : (charging ? " " : icon()) + " BAT " + pct + "%"
    color: charging || pct > 30 ? Theme.green : (pct > 15 ? Theme.orange : Theme.red)

    function icon() {
        if (pct > 80) return "";
        if (pct > 60) return "";
        if (pct > 40) return "";
        if (pct > 20) return "";
        return "";
    }
}
