-- min (dybdeskarphet/min.nvim) — theme-mode family. theme-sync calls setup()
-- with the flavor, contrast and mode before each :colorscheme, so there are no
-- opts here. Loads eagerly (lazy = false, priority = 1000) so it's on the rtp
-- before theme-sync.start().
return {
  "dybdeskarphet/min.nvim",
  lazy = false,
  priority = 1000,
}
