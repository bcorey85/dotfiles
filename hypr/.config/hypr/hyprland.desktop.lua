hl.env("LIBVA_DRIVER_NAME", "nvidia")
hl.env("GBM_BACKEND", "nvidia-drm")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")

-- ICC is generated per-machine from the monitor's EDID by scripts/.local/bin/edid-icc
-- (the AW3821DW has no sRGB clamp in its OSD, so the compositor has to do it).
-- Hyprland requires an absolute path here and forces sdr_eotf = sRGB when an ICC is set.
hl.monitor({
    output   = "DP-4",
    mode     = "3840x1600@144",
    position = "auto",
    scale    = 1.25,
    icc      = os.getenv("HOME") .. "/.local/share/icc/Dell-AW3821DW-edid.icc",
})
