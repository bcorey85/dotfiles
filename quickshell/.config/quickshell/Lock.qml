pragma Singleton

// Session lock, replacing hyprlock — the last dark-only hardcoded-hex config
// on the machine. Uses the Wayland session-lock protocol, so the compositor
// (not this process) is what keeps the screen covered: a crash here leaves the
// session locked rather than exposed.
//
// Auth is PAM, same as hyprlock's. `secure` is the compositor's own
// confirmation that the lock is actually up; the surface shows it so a lock
// that failed to engage is visible rather than silent.
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Pam
import QtQuick

Singleton {
    id: root

    property bool locked: false

    WlSessionLock {
        id: lock
        locked: root.locked

        WlSessionLockSurface {
            id: surface

            property string password: ""
            property string status: ""
            property bool busy: false

            color: Theme.bg

            function submit() {
                if (surface.busy || surface.password === "")
                    return;
                surface.busy = true;
                surface.status = "";
                if (!pam.start()) {
                    surface.busy = false;
                    surface.status = "PAM failed to start";
                }
            }

            PamContext {
                id: pam

                // PAM asks for the password through a conversation message
                // rather than up front, so the typed value is held until it
                // does. respond() with nothing at all would count as a try.
                onPamMessage: {
                    if (pam.responseRequired)
                        pam.respond(surface.password);
                }

                onCompleted: result => {
                    surface.busy = false;
                    surface.password = "";
                    if (result === PamResult.Success) {
                        root.locked = false;
                    } else {
                        surface.status = result === PamResult.MaxTries ? "Too many attempts" : "Incorrect password";
                    }
                }

                onError: err => {
                    surface.busy = false;
                    surface.password = "";
                    surface.status = "Auth error: " + PamError.toString(err);
                }
            }

            SystemClock {
                id: lockClock
                precision: SystemClock.Minutes
            }

            Column {
                anchors.centerIn: parent
                spacing: 28
                width: 360

                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.formatDateTime(lockClock.date, "hh:mm AP")
                    color: Theme.fg
                    font.family: Theme.fontFamily
                    font.pixelSize: 72
                }

                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.formatDateTime(lockClock.date, "dddd, MMMM d")
                    color: Theme.muted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize + 2
                }

                Rectangle {
                    width: parent.width
                    height: 44
                    radius: 8
                    color: Theme.panel
                    border.width: 1
                    border.color: surface.status !== "" ? Theme.red : (input.activeFocus ? Theme.accent : Theme.border)

                    Behavior on border.color { ColorAnimation { duration: 140 } }

                    TextInput {
                        id: input
                        anchors.fill: parent
                        anchors.margins: 12
                        verticalAlignment: TextInput.AlignVCenter
                        echoMode: TextInput.Password
                        passwordCharacter: "•"
                        enabled: !surface.busy
                        color: Theme.fg
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize + 2
                        selectionColor: Theme.accent

                        // The lock surface is the only thing on screen, so
                        // there is nothing else that should hold the keyboard.
                        focus: true
                        Component.onCompleted: forceActiveFocus()

                        text: surface.password
                        onTextChanged: {
                            surface.password = text;
                            if (text !== "")
                                surface.status = "";
                        }

                        Keys.onReturnPressed: surface.submit()
                        Keys.onEnterPressed: surface.submit()

                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            visible: input.text === "" && !surface.busy
                            text: "Password"
                            color: Theme.muted
                            font: input.font
                        }
                    }
                }

                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: surface.busy ? "Checking…" : surface.status
                    color: surface.status !== "" ? Theme.red : Theme.muted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize
                    height: Theme.fontSize + 4
                }
            }

            // If the compositor never confirmed the lock, say so — otherwise a
            // half-engaged lock looks identical to a working one.
            Text {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottomMargin: 24
                visible: !lock.secure
                text: "lock not confirmed by compositor"
                color: Theme.red
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSize - 1
            }
        }
    }

    IpcHandler {
        target: "lock"

        function lock(): void {
            root.locked = true;
        }
    }
}
