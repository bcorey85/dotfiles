import Quickshell
import QtQuick

// Dropdown for a bar module. grabFocus is what dismisses it on an outside
// click; the compositor swallows that click, so the bar item that opened the
// popup never sees it — toggle() ignores a click landing right after a hide,
// otherwise clicking the opener would close and immediately reopen.
PopupWindow {
    id: popup

    property double lastHide: 0

    grabFocus: true
    color: "transparent"
    visible: false

    // The window itself pops in with no transition the compositor will animate,
    // so the fade is applied to the content item — which every module fills
    // with a single rounded panel, so one animation here covers all of them.
    NumberAnimation {
        id: fadeIn
        target: popup.contentItem
        property: "opacity"
        from: 0
        to: 1
        duration: 120
        easing.type: Easing.OutCubic
    }

    onVisibleChanged: {
        if (visible)
            fadeIn.restart();
        else
            lastHide = Date.now();
    }

    function toggle() {
        if (Date.now() - lastHide < 150)
            return;
        visible = !visible;
    }
}
