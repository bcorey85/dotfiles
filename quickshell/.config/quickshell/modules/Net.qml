import Quickshell.Networking
import ".."

BarItem {
    readonly property var dev: {
        const list = Networking.devices.values;
        // Prefer a connected device; wifi wins over wired only if wired is down.
        return list.find(d => d.connected && d.type === DeviceType.Wifi)
            ?? list.find(d => d.connected)
            ?? null;
    }
    readonly property var wifiNet: dev?.networks?.values?.find(n => n.connected) ?? null

    text: {
        if (!dev) return "  Disconnected";
        if (dev.type === DeviceType.Wifi && wifiNet)
            return "  WiFi " + Math.round(wifiNet.signalStrength) + "%";
        return "  " + (dev.address || dev.name);
    }
    color: dev ? Theme.teal : Theme.red
}
