-- Shared Hyprland config (Lua, Hyprland 0.55+). Machine-specific monitors and
-- env vars live in machine.lua (symlinked per host via install/hyprland).
pcall(require, "machine")


------------------
---- MONITORS ----
------------------

-- Machine-specific monitors defined in machine.lua
-- Fallback: any unknown display uses preferred resolution at auto position
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = "auto",
})

hl.config({
    xwayland = {
        force_zero_scaling = true,
    },
})


---------------------
---- MY PROGRAMS ----
---------------------

local terminal    = "ghostty"
local fileManager = "thunar"
local menu        = "rofi -show drun"


-------------------
---- AUTOSTART ----
-------------------

hl.on("hyprland.start", function()
    -- Authentication Agent
    hl.exec_cmd("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1")

    -- Wallpaper daemon — must be split: awww-daemon runs in the foreground.
    -- (swww was renamed to awww upstream in 0.12; the Arch package followed.)
    hl.exec_cmd("awww-daemon")
    hl.exec_cmd("sleep 0.5 && hypr-wallpaper")

    -- Notification daemon
    hl.exec_cmd("dunst")

    -- Status bar
    hl.exec_cmd("waybar")

    -- Idle daemon (auto-lock & screen off)
    hl.exec_cmd("hypridle")

    -- Night light
    hl.exec_cmd("hyprsunset")

    -- Battery monitor — only on machines that have a battery
    hl.exec_cmd([[ls /sys/class/power_supply/BAT* >/dev/null 2>&1 && exec batsignal -b -w 20 -c 10 -d 5 -D "systemctl suspend"]])

    -- Clipboard manager - stores clipboard history
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")

    -- GTK theme set via gsettings (Adwaita-dark preferred)
    hl.exec_cmd("gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'")
end)


-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------

hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORMTHEME", "qt5ct")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")


-----------------------
----- PERMISSIONS -----
-----------------------

-- See https://wiki.hypr.land/Configuring/Advanced-and-Cool/Permissions/
-- Please note permission changes here require a Hyprland restart and are not applied on-the-fly
-- for security reasons

-- hl.config({
--   ecosystem = {
--     enforce_permissions = true,
--   },
-- })

-- hl.permission("/usr/(bin|local/bin)/grim", "screencopy", "allow")
-- hl.permission("/usr/(lib|libexec|lib64)/xdg-desktop-portal-hyprland", "screencopy", "allow")
-- hl.permission("/usr/(bin|local/bin)/hyprpm", "plugin", "allow")


-----------------------
---- LOOK AND FEEL ----
-----------------------

hl.config({
    general = {
        gaps_in  = 5,
        gaps_out = 20,

        border_size = 2,

        col = {
            -- kanagawa "wave" palette (dark-only, no mode axis).
            active_border   = "rgba(727169ee)",
            inactive_border = "rgba(2a2a37ee)",
        },

        resize_on_border = true,

        allow_tearing = false,

        layout = "dwindle",
    },

    decoration = {
        rounding       = 6,
        rounding_power = 2,

        active_opacity   = 1.0,
        inactive_opacity = 1.0,

        shadow = {
            enabled      = true,
            range        = 4,
            render_power = 3,
            color        = "rgba(181820ee)",
        },

        blur = {
            enabled  = true,
            size     = 3,
            passes   = 1,

            vibrancy = 0.1696,
        },
    },

    animations = {
        enabled = true,
    },
})

--            NAME              TYPE                X0,Y0          X1,Y1
hl.curve("easeOutQuint",   { type = "bezier", points = { {0.23, 1},    {0.32, 1} } })
hl.curve("easeInOutCubic", { type = "bezier", points = { {0.65, 0.05}, {0.36, 1} } })
hl.curve("linear",         { type = "bezier", points = { {0, 0},       {1, 1}    } })
hl.curve("almostLinear",   { type = "bezier", points = { {0.5, 0.5},   {0.75, 1} } })
hl.curve("quick",          { type = "bezier", points = { {0.15, 0},    {0.1, 1}  } })

hl.animation({ leaf = "global",        enabled = true, speed = 10,   bezier = "default" })
hl.animation({ leaf = "border",        enabled = true, speed = 5.39, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows",       enabled = true, speed = 4.79, bezier = "easeOutQuint" })
hl.animation({ leaf = "windowsIn",     enabled = true, speed = 4.1,  bezier = "easeOutQuint", style = "popin 87%" })
hl.animation({ leaf = "windowsOut",    enabled = true, speed = 1.49, bezier = "linear",       style = "popin 87%" })
hl.animation({ leaf = "fadeIn",        enabled = true, speed = 1.73, bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut",       enabled = true, speed = 1.46, bezier = "almostLinear" })
hl.animation({ leaf = "fade",          enabled = true, speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers",        enabled = true, speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn",      enabled = true, speed = 4,    bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut",     enabled = true, speed = 1.5,  bezier = "linear",       style = "fade" })
hl.animation({ leaf = "fadeLayersIn",  enabled = true, speed = 1.79, bezier = "almostLinear" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 1.39, bezier = "almostLinear" })
hl.animation({ leaf = "workspaces",    enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesIn",  enabled = true, speed = 1.21, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesOut", enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "zoomFactor",    enabled = true, speed = 7,    bezier = "quick" })

-- Remove gaps, borders, and rounding when only one tiled window
hl.workspace_rule({ workspace = "w[tv1]", gaps_out = 0, gaps_in = 0, no_border = true, no_rounding = true })
hl.workspace_rule({ workspace = "f[1]",   gaps_out = 0, gaps_in = 0, no_border = true, no_rounding = true })

hl.config({
    dwindle = {
        preserve_split = true,
    },

    master = {
        new_status = "master",
    },

    misc = {
        force_default_wallpaper = 0,
        disable_hyprland_logo   = true,
    },
})


---------------
---- INPUT ----
---------------

hl.config({
    input = {
        numlock_by_default = true,
        kb_layout  = "us,us",
        kb_variant = "",
        kb_model   = "",
        kb_options = "ctrl:nocaps",
        kb_rules   = "",

        follow_mouse = 1,

        sensitivity = 0,

        touchpad = {
            disable_while_typing = true,
            natural_scroll       = false,
            clickfinger_behavior = true,
            tap_to_click         = true,
            drag_lock            = false,
            tap_and_drag         = true,
        },
    },
})

hl.gesture({
    fingers   = 3,
    direction = "horizontal",
    action    = "workspace",
})


---------------------
---- KEYBINDINGS ----
---------------------

local mainMod = "SUPER"

-----------------------------
---- WINDOW MANAGEMENT ----
-----------------------------

hl.bind(mainMod .. " + Return",    hl.dsp.exec_cmd(terminal),                              { description = "Open terminal" })
hl.bind(mainMod .. " + W",         hl.dsp.window.close(),                                  { description = "Close focused window" })
hl.bind(mainMod .. " + F1",        hl.dsp.exec_cmd("hyprctl switchxkblayout all next"),    { description = "Toggle keyboard layout" })
hl.bind(mainMod .. " + F",         hl.dsp.window.fullscreen({ mode = "fullscreen" }),      { description = "Fullscreen" })
hl.bind(mainMod .. " + SHIFT + F", hl.dsp.window.fullscreen({ mode = "maximized" }),       { description = "Fullscreen (full width)" })
hl.bind(mainMod .. " + T",         hl.dsp.window.float({ action = "toggle" }),             { description = "Toggle floating" })
hl.bind(mainMod .. " + backslash", hl.dsp.layout("togglesplit"),                           { description = "Toggle split direction" })
hl.bind(mainMod .. " + P",         hl.dsp.window.pseudo(),                                 { description = "Pseudo tile" })

-- Move focus (hjkl + arrows)
hl.bind(mainMod .. " + H",     hl.dsp.focus({ direction = "left" }),  { description = "Move focus left" })
hl.bind(mainMod .. " + L",     hl.dsp.focus({ direction = "right" }), { description = "Move focus right" })
hl.bind(mainMod .. " + K",     hl.dsp.focus({ direction = "up" }),    { description = "Move focus up" })
hl.bind(mainMod .. " + J",     hl.dsp.focus({ direction = "down" }),  { description = "Move focus down" })
hl.bind(mainMod .. " + left",  hl.dsp.focus({ direction = "left" }),  { description = "Move focus left" })
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }), { description = "Move focus right" })
hl.bind(mainMod .. " + up",    hl.dsp.focus({ direction = "up" }),    { description = "Move focus up" })
hl.bind(mainMod .. " + down",  hl.dsp.focus({ direction = "down" }),  { description = "Move focus down" })

-- Swap windows
hl.bind(mainMod .. " + SHIFT + left",  hl.dsp.window.swap({ direction = "left" }),  { description = "Swap window left" })
hl.bind(mainMod .. " + SHIFT + right", hl.dsp.window.swap({ direction = "right" }), { description = "Swap window right" })
hl.bind(mainMod .. " + SHIFT + up",    hl.dsp.window.swap({ direction = "up" }),    { description = "Swap window up" })
hl.bind(mainMod .. " + SHIFT + down",  hl.dsp.window.swap({ direction = "down" }),  { description = "Swap window down" })

-- Resize windows
hl.bind(mainMod .. " + equal", hl.dsp.layout("splitratio 0.1"),  { description = "Grow window",   repeating = true })
hl.bind(mainMod .. " + minus", hl.dsp.layout("splitratio -0.1"), { description = "Shrink window", repeating = true })

-- Scratchpad
hl.bind(mainMod .. " + S",       hl.dsp.workspace.toggle_special("magic"),             { description = "Toggle scratchpad" })
hl.bind(mainMod .. " + ALT + S", hl.dsp.window.move({ workspace = "special:magic" }),  { description = "Move to scratchpad" })

------------------------
---- WORKSPACE NAV ----
------------------------

-- Switch with mainMod + [0-9], move window with mainMod + SHIFT + [0-9]
for i = 1, 10 do
    local key = i % 10 -- 10 maps to key 0
    hl.bind(mainMod .. " + " .. key,           hl.dsp.focus({ workspace = i }),       { description = "Switch to workspace " .. i })
    hl.bind(mainMod .. " + SHIFT + " .. key,   hl.dsp.window.move({ workspace = i }), { description = "Move window to workspace " .. i })
end

hl.bind(mainMod .. " + Tab",         hl.dsp.focus({ workspace = "e+1" }),      { description = "Next workspace" })
hl.bind(mainMod .. " + SHIFT + Tab", hl.dsp.focus({ workspace = "e-1" }),      { description = "Previous workspace" })
hl.bind(mainMod .. " + code:47",     hl.dsp.focus({ workspace = "previous" }), { description = "Toggle last workspace" })

-- Alt-Tab window cycling
hl.bind("ALT + Tab",         hl.dsp.window.cycle_next(),                { description = "Cycle to next window" })
hl.bind("ALT + SHIFT + Tab", hl.dsp.window.cycle_next({ next = false }), { description = "Cycle to previous window" })

-- Scroll through workspaces
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), { description = "Scroll workspaces forward" })
hl.bind(mainMod .. " + mouse_up",   hl.dsp.focus({ workspace = "e-1" }), { description = "Scroll workspaces backward" })

-------------------------
---- APP LAUNCHERS ----
-------------------------

hl.bind(mainMod .. " + Space",         hl.dsp.exec_cmd(menu),                                                        { description = "Open app launcher" })
hl.bind(mainMod .. " + SHIFT + B",     hl.dsp.exec_cmd("google-chrome-stable"),                                      { description = "Open browser" })
hl.bind(mainMod .. " + SHIFT + N",     hl.dsp.exec_cmd(terminal .. " -e nvim"),                                      { description = "Open Neovim" })
hl.bind(mainMod .. " + E",             hl.dsp.exec_cmd(fileManager),                                                 { description = "Open file manager" })
hl.bind(mainMod .. " + SHIFT + D",     hl.dsp.exec_cmd(terminal .. " -e lazydocker"),                                { description = "Open Lazydocker" })
hl.bind(mainMod .. " + SHIFT + G",     hl.dsp.exec_cmd(terminal .. " -e lazygit"),                                   { description = "Open Lazygit" })
hl.bind(mainMod .. " + SHIFT + A",     hl.dsp.exec_cmd("google-chrome-stable --new-window https://claude.ai/new"),   { description = "Open Claude.ai" })
hl.bind(mainMod .. " + SHIFT + M",     hl.dsp.exec_cmd("plexamp"),                                                   { description = "Open Plexamp" })
hl.bind(mainMod .. " + SHIFT + comma", hl.dsp.exec_cmd(terminal .. " -e nvim ~/.config/hypr/hyprland.lua"),          { description = "Edit Hyprland config" })

-----------------------
---- SCREENSHOTS ----
-----------------------

hl.bind(mainMod .. " + SHIFT + S", hl.dsp.exec_cmd("bash ~/.local/bin/hypr-screenshot region"), { description = "Screenshot region" })
hl.bind("Print",                   hl.dsp.exec_cmd("bash ~/.local/bin/hypr-screenshot"),        { description = "Screenshot fullscreen" })
hl.bind(mainMod .. " + Print",     hl.dsp.exec_cmd("bash ~/.local/bin/hypr-screenshot region"), { description = "Screenshot region" })

--------------------
---- SYSTEM ----
--------------------

hl.bind(mainMod .. " + Escape",       hl.dsp.exec_cmd("bash ~/.local/bin/hypr-power-menu"),                                     { description = "Power menu" })
hl.bind(mainMod .. " + CTRL + L",     hl.dsp.exec_cmd("hyprlock"),                                                              { description = "Lock screen" })
hl.bind(mainMod .. " + CTRL + A",     hl.dsp.exec_cmd("pavucontrol"),                                                           { description = "Audio controls" })
hl.bind(mainMod .. " + CTRL + K",     hl.dsp.exec_cmd("hyprctl switchxkblayout all next"),                                      { description = "Toggle keyboard layout" })
hl.bind(mainMod .. " + CTRL + Space", hl.dsp.exec_cmd("bash ~/.local/bin/hypr-wallpaper"),                                      { description = "Cycle wallpaper" })
hl.bind(mainMod .. " + CTRL + V",     hl.dsp.exec_cmd([[cliphist list | rofi -dmenu -p "Clipboard" | cliphist decode | wl-copy]]), { description = "Clipboard history" })
hl.bind(mainMod .. " + slash",        hl.dsp.exec_cmd("bash ~/.local/bin/hypr-which-key"),                                      { description = "Show keybindings" })
hl.bind(mainMod .. " + SHIFT + C",    hl.dsp.exec_cmd("hyprpicker -a"),                                                         { description = "Pick color to clipboard" })

-- Mouse
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Media keys
hl.bind("XF86AudioRaiseVolume",   hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"),  { description = "Raise volume",        locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume",   hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),       { description = "Lower volume",        locked = true, repeating = true })
hl.bind("XF86AudioMute",          hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),      { description = "Mute audio",          locked = true, repeating = true })
hl.bind("XF86AudioMicMute",       hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),    { description = "Mute microphone",     locked = true, repeating = true })
hl.bind("XF86MonBrightnessUp",    hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"),                   { description = "Increase brightness", locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown",  hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"),                   { description = "Decrease brightness", locked = true, repeating = true })
hl.bind("XF86AudioNext",          hl.dsp.exec_cmd("playerctl next"),                                  { description = "Next track",          locked = true })
hl.bind("XF86AudioPause",         hl.dsp.exec_cmd("playerctl play-pause"),                            { description = "Pause/play",          locked = true })
hl.bind("XF86AudioPlay",          hl.dsp.exec_cmd("playerctl play-pause"),                            { description = "Play/pause",          locked = true })
hl.bind("XF86AudioPrev",          hl.dsp.exec_cmd("playerctl previous"),                              { description = "Previous track",      locked = true })


--------------------------------
---- WINDOWS AND WORKSPACES ----
--------------------------------

hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = ".*" },

    suppress_event = "maximize",
})

hl.window_rule({
    name  = "fix-xwayland-drags",
    match = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
        pin        = false,
    },

    no_focus = true,
})

hl.window_rule({
    name  = "float-dialogs",
    match = { title = "^(Open|Open File|Save|Save As|Save File|Rename|Delete|Confirm|Replace|Properties|Preferences|Settings|About)(.*)$" },

    float  = true,
    center = true,
})

hl.window_rule({
    name  = "float-dialog-classes",
    match = { class = "^(file_progress|confirm|dialog|notification|splash|pinentry|pavucontrol|org.gnome.Calculator|xdg-desktop-portal-gtk|polkit-gnome-authentication-agent-1)$" },

    float  = true,
    center = true,
})

hl.window_rule({
    name  = "float-polkit",
    match = { class = "^(org.freedesktop.impl.portal.desktop.gtk|org.freedesktop.impl.portal.desktop.hyprland)$" },

    float  = true,
    center = true,
})

hl.window_rule({
    name  = "wow-fullscreen",
    match = { class = "steam_app_default" },

    fullscreen     = true,
    suppress_event = "fullscreen activate activatefocus",
})

hl.window_rule({
    name  = "move-hyprland-run",
    match = { class = "hyprland-run" },

    move  = "20 monitor_h-120",
    float = true,
})

hl.window_rule({
    name  = "vesktop-workspace",
    match = { class = "^(vesktop)$" },

    -- silent = land on ws 3 without stealing focus, even if it maps slowly
    workspace = "3 silent",
})

hl.window_rule({
    name  = "lutris-workspace",
    match = { class = "^(net\\.lutris\\.Lutris)$" },

    workspace = "2 silent",
})
