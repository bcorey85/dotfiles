# Auto-start Hyprland on tty1 — only for an interactive login with no
# session already running (guards against non-interactive tool shells).
if [[ $- == *i* ]] && [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = 1 ]; then
    exec start-hyprland
fi
