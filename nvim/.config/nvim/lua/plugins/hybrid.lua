-- hybrid (HoNamDuong/hybrid.nvim) — theme-mode family. Dark #1d1f21 is the plugin's
-- own colorscheme "hybrid". The plugin is dark only: light is colors/hybrid-light.lua,
-- which runs the same highlight table over a Tomorrow palette. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before theme-sync.start().
return {
  "HoNamDuong/hybrid.nvim",
  lazy = false,
  priority = 1000,
  opts = {
    bold = false,
    italic = { strings = false, emphasis = false, comments = false, folds = false },
  },
}
