-- ember (ember-theme/nvim) — theme-mode family. Warm near-monochrome with one
-- coral accent: "ember" graphite #1c1b19 dark / "ember-light" parchment
-- #e6dac4 light — the darkest and the warmest of its four variants
-- (ember-soft is a lifted graphite, ember-lighter a cooler ivory). Loads
-- eagerly (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
--
-- One colorscheme per variant, each registering its own colors_name, so
-- theme-sync names them separately and needs no colors_name pin.
return {
  "ember-theme/nvim",
  name = "ember",
  lazy = false,
  priority = 1000,
}
