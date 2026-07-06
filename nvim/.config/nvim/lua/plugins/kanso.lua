-- kanso — stock, no overrides. Audition against the customized kanagawa
-- dragon (kanagawa.lua): kanso reuses dragon's ink (#c5c9c7) and accent set
-- on its own canvases — ink #14171d (L=0.009), mist #22262d (L=0.019) — so
-- it's the zero-customization version of the same look, with a cool cast.
-- dark = kanso-ink, light = kanso-pearl via lua/config/theme-sync.lua.
return {
  "webhooked/kanso.nvim",
  lazy = false,
  priority = 1000,
}
