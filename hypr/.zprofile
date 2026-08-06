# Lives in the arch-only `hypr` package, not `zsh`: macOS keeps a machine-local
# ~/.zprofile (MacPorts/pyenv PATH), and shipping this one there both clobbers
# that and stows a Hyprland launcher onto a machine with no Hyprland.
#
# Auto-start Hyprland on tty1 — only for an interactive login with no
# session already running (guards against non-interactive tool shells).
if [[ $- == *i* ]] && [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = 1 ]; then
    exec start-hyprland
fi
