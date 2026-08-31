import Quickshell

ShellRoot {
    // One bar per monitor.
    Variants {
        model: Quickshell.screens
        delegate: Bar {}
    }

    // The notification daemon (Notifs singleton) plus this popup layer replace
    // dunst outright — nothing else may own the bus name.
    Notifications {}

    // Media-key feedback: volume, mic mute, brightness.
    Osd {}

    // Apps, clipboard, calc and the power menu — opened over IPC from
    // hyprland.lua.
    Launcher {}

    // Singletons are created on first use, so the session lock has to be
    // referenced here or its IpcHandler never registers and `qs ipc call lock`
    // fails until something else happens to touch it.
    readonly property var sessionLock: Lock
}
