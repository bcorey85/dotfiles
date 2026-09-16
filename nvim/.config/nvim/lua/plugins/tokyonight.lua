-- tokyonight (folke/tokyonight.nvim) — theme-mode family. Storm #24283b dark /
-- day #e1e2e7 light. Loads eagerly (lazy = false, priority = 1000) so it's on
-- the rtp before config.lazy.lua's theme-sync.start().
return {
  "folke/tokyonight.nvim",
  name = "tokyonight",
  lazy = false,
  priority = 1000,
}
