-- solarized-osaka (craftzdog/solarized-osaka.nvim) — theme-mode family. Base04 #001419 dark /
-- base3 #fdf6e2 light. Loads eagerly (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
return {
  "craftzdog/solarized-osaka.nvim",
  lazy = false,
  priority = 1000,
}
