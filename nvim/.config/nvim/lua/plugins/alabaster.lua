-- alabaster (p00f/alabaster.nvim) — theme-mode family. One colorscheme that follows
-- 'background': dark #0e1415, light #f7f7f7. Loads eagerly (lazy = false, priority = 1000)
-- so it's on the rtp before config.lazy.lua's theme-sync.start().
return {
  "p00f/alabaster.nvim",
  lazy = false,
  priority = 1000,
}
