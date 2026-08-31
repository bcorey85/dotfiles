import Quickshell
import QtQuick
import ".."

// Bell in the bar: click for history, right-click toggles do-not-disturb.
// This is the piece dunst only had as `dunstctl history-pop`.
Item {
    id: root

    implicitWidth: label.implicitWidth + 20
    implicitHeight: parent ? parent.height : Theme.barHeight

    Rectangle {
        anchors.fill: parent
        color: mouse.containsMouse ? Theme.panel : "transparent"
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: Notifs.dnd ? "󰂛" : (Notifs.history.length > 0 ? "󰂚 " + Notifs.history.length : "󰂜")
        color: Notifs.dnd ? Theme.muted : (Notifs.live.values.length > 0 ? Theme.accent : Theme.fg)
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouseEvent => {
            if (mouseEvent.button === Qt.RightButton) Notifs.dnd = !Notifs.dnd;
            else popup.toggle();
        }
    }

    BarPopup {
        id: popup
        anchor.window: QsWindow.window
        anchor.rect.x: root.x - 320 + root.width
        anchor.rect.y: root.y + root.height
        implicitWidth: 380
        implicitHeight: Math.min(500, panel.implicitHeight)

        Rectangle {
            anchors.fill: parent
            color: Theme.panel
            border.color: Theme.border
            border.width: 1
            radius: 8

            Column {
                id: panel
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Row {
                    width: parent.width
                    spacing: 8

                    Text {
                        text: "Notifications"
                        color: Theme.fg
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize
                        font.bold: true
                    }

                    Item {
                        width: parent.width - 200
                        height: 1
                    }

                    Text {
                        text: Notifs.dnd ? "DND on" : "DND off"
                        color: Notifs.dnd ? Theme.orange : Theme.muted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize - 2

                        MouseArea {
                            anchors.fill: parent
                            onClicked: Notifs.dnd = !Notifs.dnd
                        }
                    }

                    Text {
                        text: "Clear"
                        color: Theme.red
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSize - 2

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                Notifs.dismissAll();
                                Notifs.clearHistory();
                            }
                        }
                    }
                }

                Text {
                    visible: Notifs.history.length === 0
                    text: "Nothing yet"
                    color: Theme.muted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize - 1
                }

                ListView {
                    width: parent.width
                    height: Math.min(420, contentHeight)
                    clip: true
                    spacing: 8
                    model: Notifs.history

                    delegate: Item {
                        id: entry
                        required property var modelData

                        width: ListView.view.width
                        height: Math.max(entryText.implicitHeight, entryIcon.height)

                        NotifIcon {
                            id: entryIcon
                            anchors.left: parent.left
                            anchors.top: parent.top
                            image: entry.modelData.image
                            appIcon: entry.modelData.appIcon
                        }

                        Column {
                            id: entryText
                            anchors.left: entryIcon.visible ? entryIcon.right : parent.left
                            anchors.leftMargin: entryIcon.visible ? 8 : 0
                            anchors.right: parent.right
                            spacing: 2

                            Text {
                                width: parent.width
                                text: Qt.formatDateTime(entry.modelData.time, "hh:mm") + "  " + entry.modelData.appName
                                color: Theme.muted
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSize - 3
                                elide: Text.ElideRight
                            }

                            Text {
                                width: parent.width
                                text: entry.modelData.summary
                                color: Theme.fg
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSize - 1
                                elide: Text.ElideRight
                            }

                            Text {
                                width: parent.width
                                visible: text !== ""
                                text: entry.modelData.body
                                color: Theme.muted
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSize - 2
                                wrapMode: Text.Wrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                textFormat: Text.PlainText
                            }
                        }
                    }
                }
            }
        }
    }
}
