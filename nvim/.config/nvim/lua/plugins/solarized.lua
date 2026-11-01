-- solarized (maxmx03/solarized.nvim) — theme-mode family. One colorscheme that follows
-- 'background': base03 #002b36 dark, base3 #fdf6e3 light. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before config.lazy.lua's theme-sync.start().
return {
  "maxmx03/solarized.nvim",
  lazy = false,
  priority = 1000,
}
