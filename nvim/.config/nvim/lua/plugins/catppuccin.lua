-- catppuccin (catppuccin/nvim) — theme-mode family. Mocha #1e1e2e dark /
-- latte #eff1f5 light. Loads eagerly (lazy = false, priority = 1000) so it's on
-- the rtp before config.lazy.lua's theme-sync.start().
return {
  "catppuccin/nvim",
  name = "catppuccin",
  lazy = false,
  priority = 1000,
}
