-- gruvbox (ellisonleao/gruvbox.nvim) — theme-mode family. ORIGINAL gruvbox,
-- medium contrast: #282828 dark / #fbf1c7 cream light. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before config.lazy.lua's
-- theme-sync.start(). One colorscheme "gruvbox" follows vim.o.background, so
-- theme-sync pins both.
--
-- NOT sainnhe/gruvbox-material: that is a separate, softer palette (red
-- #f2594b vs original #fb4934, fg #e2cca9 vs #ebdbb2). The hunk/herdr/starship
-- gruvbox blocks encode the ORIGINAL hexes.
return {
  "ellisonleao/gruvbox.nvim",
  name = "gruvbox",
  lazy = false,
  priority = 1000,
}
