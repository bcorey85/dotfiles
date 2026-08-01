hl.env("LIBVA_DRIVER_NAME", "nvidia")
hl.env("GBM_BACKEND", "nvidia-drm")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")

hl.monitor({
    output   = "DP-4",
    mode     = "3840x1600@144",
    position = "auto",
    scale    = 1.25,
})
