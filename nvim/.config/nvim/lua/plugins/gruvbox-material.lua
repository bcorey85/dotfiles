-- gruvbox-material (sainnhe/gruvbox-material) — theme-mode family, run with
-- `background = "soft"` and `foreground = "material"`.
--
-- Loads eagerly (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start(). The variant globals are set by
-- theme-sync's `pre` hook, which runs before :colorscheme.
return {
  "sainnhe/gruvbox-material",
  name = "gruvbox-material",
  lazy = false,
  priority = 1000,
}
