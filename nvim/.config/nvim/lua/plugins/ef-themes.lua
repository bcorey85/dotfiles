-- ef-themes (oonamo/ef-themes.nvim, port of Protesilaos's Emacs ef-themes) —
-- theme-mode families ef-elea and ef-maris. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before config.lazy.lua's theme-sync.start().
-- The other themes stay reachable by hand: :colorscheme ef-owl, ef-frost, ...
return {
  "oonamo/ef-themes.nvim",
  name = "ef-themes",
  lazy = false,
  priority = 1000,
}
