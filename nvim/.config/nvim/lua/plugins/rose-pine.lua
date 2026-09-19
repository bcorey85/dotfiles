-- rose-pine (rose-pine/neovim) — theme-mode family. Moon #232136 dark / dawn
-- #faf4ed light. Loads eagerly (lazy = false, priority = 1000) so it's on the
-- rtp before config.lazy.lua's theme-sync.start().
return {
  "rose-pine/neovim",
  name = "rose-pine",
  lazy = false,
  priority = 1000,
}
