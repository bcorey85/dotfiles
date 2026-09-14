-- kanagawa (rebelot/kanagawa.nvim) — theme-mode family. Blue-ink
-- "wave" #1f1f28 dark / warm cream "lotus" #f2ecbc light. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
--
-- Unlike the other families, kanagawa ships one colorscheme PER variant
-- ("kanagawa-wave" / "kanagawa-lotus") rather than switching on
-- vim.o.background, so theme-sync names them separately.
return {
  "rebelot/kanagawa.nvim",
  name = "kanagawa",
  lazy = false,
  priority = 1000,
}
