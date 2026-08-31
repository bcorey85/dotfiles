-- kanagawa (rebelot/kanagawa.nvim) — theme-mode family. Warm charcoal
-- "dragon" #181616 dark / warm cream "lotus" #f2ecbc light. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
--
-- Unlike the other families, kanagawa ships one colorscheme PER variant
-- ("kanagawa-dragon" / "kanagawa-lotus") rather than switching on
-- vim.o.background, so theme-sync names them separately.
return {
  "rebelot/kanagawa.nvim",
  name = "kanagawa",
  lazy = false,
  priority = 1000,
}
