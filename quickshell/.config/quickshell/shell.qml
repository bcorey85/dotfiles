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

    // Apps, clipboard and calc — opened over IPC from hyprland.lua.
    Launcher {}
}
