-- melange (savq/melange-nvim) — theme-mode family. Warm brown-black #292522
-- dark / neutral #f1f1f1 light. Loads eagerly (lazy = false, priority = 1000)
-- so it's on the rtp before config.lazy.lua's theme-sync.start(). One
-- colorscheme "melange" follows vim.o.background, so theme-sync pins both.
return {
  "savq/melange-nvim",
  name = "melange",
  lazy = false,
  priority = 1000,
}
