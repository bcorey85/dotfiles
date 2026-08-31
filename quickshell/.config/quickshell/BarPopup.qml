import Quickshell

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

    onVisibleChanged: if (!visible) lastHide = Date.now()

    function toggle() {
        if (Date.now() - lastHide < 150)
            return;
        visible = !visible;
    }
}
