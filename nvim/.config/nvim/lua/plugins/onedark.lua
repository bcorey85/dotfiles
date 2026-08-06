-- onedark (navarasu/onedark.nvim), one of two theme families (the other is
-- lua/plugins/kanagawa.lua) — a plain declarative spec. It loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start() call, which is the sole bootstrap
-- owner. The dark/light variant comes from setup{style=...}, called by
-- theme-sync's `pre` hook — do not call setup here, it would race the
-- sync's own call.
return {
  "navarasu/onedark.nvim",
  lazy = false,
  priority = 1000,
}
