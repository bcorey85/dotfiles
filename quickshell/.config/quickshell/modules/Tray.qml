import Quickshell
import Quickshell.Services.SystemTray
import Quickshell.Widgets
import QtQuick
import QtQuick.Layouts

RowLayout {
    spacing: 8

    Repeater {
        model: SystemTray.items

        IconImage {
            required property var modelData
            implicitSize: 18
            source: modelData.icon
            opacity: modelData.status === Status.Passive ? 0.5 : 1.0

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                onClicked: mouseEvent => {
                    if (mouseEvent.button === Qt.MiddleButton) parent.modelData.secondaryActivate();
                    else parent.modelData.activate();
                }
            }
        }
    }
}
