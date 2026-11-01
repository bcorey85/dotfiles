-- selenized (calind/selenized.nvim) — theme-mode family. One colorscheme that follows
-- 'background': bg_0 #103c48 dark, #fbf3db light. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before config.lazy.lua's theme-sync.start().
return {
  "calind/selenized.nvim",
  lazy = false,
  priority = 1000,
}
