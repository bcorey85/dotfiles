-- gruvbox (ellisonleao/gruvbox.nvim) — theme-mode family, medium contrast
-- (the plugin default). morhetz's palette with Treesitter and LSP groups.
-- Loads eagerly (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
--
-- One colorscheme "gruvbox" follows vim.o.background and sets colors_name
-- "gruvbox" in both modes, so theme-sync pins it.
return {
  "ellisonleao/gruvbox.nvim",
  lazy = false,
  priority = 1000,
  opts = { bold = false },
}
