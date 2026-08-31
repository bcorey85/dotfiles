import Quickshell
import QtQuick
import ".."

// Click opens a calendar drawn by this shell — the thing waybar structurally
// cannot do (its on-click can only launch gsimplecal as a foreign window).
Item {
    id: root
    implicitWidth: label.implicitWidth + 20
    implicitHeight: parent ? parent.height : Theme.barHeight

    property date now: clock.date

    SystemClock {
        id: clock
        precision: SystemClock.Minutes
    }

    Rectangle {
        anchors.fill: parent
        color: mouse.containsMouse ? Theme.panel : "transparent"
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: Qt.formatDateTime(root.now, "hh:mm AP  MM/dd/yyyy")
        color: Theme.fg
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
        font.bold: true
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: popup.toggle()
    }

    BarPopup {
        id: popup
        anchor.window: QsWindow.window
        anchor.rect.x: root.x
        anchor.rect.y: root.y + root.height
        implicitWidth: 260
        implicitHeight: cal.implicitHeight + 24

        Rectangle {
            anchors.fill: parent
            color: Theme.panel
            border.color: Theme.border
            border.width: 1
            radius: 8

            Column {
                id: cal
                anchors.centerIn: parent
                width: parent.width - 24
                spacing: 8

                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.formatDateTime(root.now, "MMMM yyyy")
                    color: Theme.fg
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSize
                    font.bold: true
                }

                Grid {
                    columns: 7
                    spacing: 2

                    Repeater {
                        model: ["S", "M", "T", "W", "T", "F", "S"]
                        Text {
                            width: 32
                            horizontalAlignment: Text.AlignHCenter
                            text: modelData
                            color: Theme.muted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSize - 2
                        }
                    }

                    // 6 weeks x 7 days covers every month layout.
                    Repeater {
                        model: 42

                        Text {
                            // Day 1 of this month, backed up to the preceding Sunday.
                            readonly property date cell: {
                                const first = new Date(root.now.getFullYear(), root.now.getMonth(), 1);
                                const d = new Date(first);
                                d.setDate(1 - first.getDay() + index);
                                return d;
                            }
                            readonly property bool thisMonth: cell.getMonth() === root.now.getMonth()
                            readonly property bool today: thisMonth && cell.getDate() === root.now.getDate()

                            width: 32
                            horizontalAlignment: Text.AlignHCenter
                            text: cell.getDate()
                            color: today ? Theme.accent : (thisMonth ? Theme.fg : Theme.muted)
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSize - 1
                            font.bold: today
                        }
                    }
                }
            }
        }
    }
}
