pragma Singleton

import Quickshell
import Quickshell.Services.Notifications

// The notification daemon: owns org.freedesktop.Notifications, the live popup
// set (trackedNotifications) and the history the bar's notification center
// reads. Nothing else may create a NotificationServer — the bus name is
// exclusive.
Singleton {
    id: root

    // Suppresses popups only. Notifications still land in history.
    property bool dnd: false

    // Newest first, capped. Plain JS array: the list is short and fully
    // replaced on every push, so a ListModel buys nothing.
    property var history: []

    readonly property var live: server.trackedNotifications

    function clearHistory() {
        root.history = [];
    }

    function dismissAll() {
        // dismiss() mutates trackedNotifications, so iterate over a copy.
        for (const n of [...server.trackedNotifications.values])
            n.dismiss();
    }

    NotificationServer {
        id: server

        actionsSupported: true
        bodySupported: true
        bodyMarkupSupported: true
        imageSupported: true
        keepOnReload: false

        onNotification: notification => {
            // Without this the server drops it.
            notification.tracked = true;

            // Dedup, as dunst did: a repeat of a notification already on screen
            // (same app, same text) replaces it instead of stacking.
            for (const old of [...server.trackedNotifications.values]) {
                if (old !== notification
                    && old.appName === notification.appName
                    && old.summary === notification.summary
                    && old.body === notification.body)
                    old.dismiss();
            }

            root.history = [
                {
                    appName: notification.appName,
                    summary: notification.summary,
                    body: notification.body,
                    image: notification.image,
                    appIcon: notification.appIcon,
                    time: new Date()
                },
                ...root.history
            ].slice(0, 50);
        }
    }
}
