-- kanagawa (rebelot/kanagawa.nvim), one of two theme families (the other is
-- lua/plugins/onedark.lua) — a plain declarative spec. It loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start() call, which is the sole bootstrap
-- owner. Variant selection needs no `setup()` call — theme-sync picks the
-- variant by colorscheme name (kanagawa-wave / kanagawa-lotus), not a
-- style global.
return {
  "rebelot/kanagawa.nvim",
  lazy = false,
  priority = 1000,
}
