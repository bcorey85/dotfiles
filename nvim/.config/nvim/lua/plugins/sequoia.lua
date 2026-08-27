-- sequoia (forest-nvim/sequoia.nvim) — theme-mode family. Sets per-variant
-- colors_name (sequoia-night/sequoia-rise), so theme-sync needs no colors_name
-- pin. Eager + high priority so the scheme is on the rtp before theme-sync's
-- first apply.
return {
  "forest-nvim/sequoia.nvim",
  name = "sequoia",
  lazy = false,
  priority = 1000,
}
