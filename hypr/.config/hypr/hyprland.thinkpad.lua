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
