-- onedark (navarasu/onedark.nvim). The only colorscheme installed, so this spec
-- doubles as the theme-sync bootstrap: it loads eagerly (lazy = false,
-- priority = 1000) and its config starts the sync, which reads
-- ~/.cache/theme-{family,mode} and applies the active variant. The dark/light
-- variant comes from setup{style=...}, called by theme-sync's `pre` hook — do
-- not call setup here, it would race the sync's own call.
return {
  "navarasu/onedark.nvim",
  lazy = false,
  priority = 1000,
  config = function()
    require("config.theme-sync").start()
  end,
}
