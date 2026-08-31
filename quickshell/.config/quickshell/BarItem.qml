// Shared chrome for every right-side module: hover wash, uniform padding,
// optional click. Modules supply `text` and `color` only.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string text: ""
    property color color: Theme.fg
    property bool clickable: false
    signal clicked

    visible: text !== ""
    Layout.fillHeight: true
    implicitWidth: visible ? label.implicitWidth + 20 : 0

    Rectangle {
        anchors.fill: parent
        color: (root.clickable && mouse.containsMouse) ? Theme.panel : "transparent"
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.color
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: root.clickable
        hoverEnabled: root.clickable
        onClicked: root.clicked()
    }
}
