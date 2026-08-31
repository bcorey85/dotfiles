import Quickshell
import Quickshell.Widgets
import Quickshell.Services.Notifications
import QtQuick

// Popup layer. The server itself lives in the Notifs singleton so the bar's
// notification center can read the same history.
PanelWindow {
    anchors.top: true
    anchors.right: true
    margins.top: 12
    margins.right: 12
    implicitWidth: 380
    implicitHeight: Math.max(1, stack.implicitHeight)
    exclusiveZone: 0
    color: "transparent"
    visible: !Notifs.dnd && Notifs.live.values.length > 0

    Column {
        id: stack
        width: parent.width
        spacing: 8

        Repeater {
            model: Notifs.live

            Rectangle {
                id: card
                required property var modelData

                // -1 means "server decides"; 0 means never expire.
                readonly property int timeout: {
                    if (card.modelData.expireTimeout > 0) return card.modelData.expireTimeout;
                    if (card.modelData.expireTimeout === 0) return 0;
                    return card.modelData.urgency === NotificationUrgency.Critical ? 0 : 6000;
                }

                width: stack.width
                height: Math.max(content.implicitHeight, icon.height) + 24
                color: Theme.panel
                border.color: card.modelData.urgency === NotificationUrgency.Critical ? Theme.red : Theme.border
                border.width: 1
                radius: 8

                NotifIcon {
                    id: icon
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    image: card.modelData.image
                    appIcon: card.modelData.appIcon
                }

                Column {
                    id: content
                    anchors.left: icon.visible ? icon.right : parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 12
                    spacing: 4

                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: card.modelData.appName
                        color: Theme.accent
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize - 3
                        elide: Text.ElideRight
                    }

                    Text {
                        width: parent.width
                        text: card.modelData.summary
                        color: Theme.fg
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize
                        font.bold: true
                        elide: Text.ElideRight
                    }

                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: card.modelData.body
                        color: Theme.muted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize - 1
                        wrapMode: Text.Wrap
                        maximumLineCount: 4
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Row {
                        spacing: 8
                        visible: card.modelData.actions.length > 0

                        Repeater {
                            model: card.modelData.actions

                            Rectangle {
                                id: action
                                required property var modelData

                                width: actionLabel.implicitWidth + 16
                                height: 24
                                radius: 4
                                color: actionMouse.containsMouse ? Theme.bg : "transparent"
                                border.color: Theme.border
                                border.width: 1

                                Text {
                                    id: actionLabel
                                    anchors.centerIn: parent
                                    text: action.modelData.text
                                    color: Theme.accent
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSize - 2
                                }

                                MouseArea {
                                    id: actionMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: action.modelData.invoke()
                                }
                            }
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                    onClicked: card.modelData.dismiss()
                    // Let the action buttons keep their left clicks.
                    z: -1
                }

                Timer {
                    running: card.timeout > 0
                    interval: card.timeout
                    onTriggered: card.modelData.expire()
                }
            }
        }
    }
}
