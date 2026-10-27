hl.monitor({
    output   = "eDP-1",
    mode     = "2880x1800@120",
    position = "auto",
    scale    = 1.8,
    -- Panel primaries exceed Display-P3 (green 0.2197,0.7246). Without this,
    -- sRGB-authored content is sent untranslated and oversaturates.
    -- "edid" maps sRGB into the panel's declared gamut; 10-bit avoids banding
    -- in the narrower post-conversion range.
    cm       = "edid",
    bitdepth = 10,
})

-- Attach to the desktop's herdr session over SSH ("pc" is a Host in ~/.ssh/config).
-- Launched from Hyprland, not a pane, so no HERDR_* vars trip herdr's nesting guard.
-- Server keybindings: with local ones, herdr drops [[keys.command]] binds (popups).
hl.bind("SUPER + SHIFT + R", hl.dsp.exec_cmd("ghostty -e " .. os.getenv("HOME") .. "/.local/bin/herdr --remote pc --remote-keybindings server"), { description = "Remote herdr on PC" })
