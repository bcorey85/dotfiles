-- thorn (jpwol/thorn.nvim) — theme-mode family. Minimal green: "forest"
-- #172526 dark / "field" cream-lime #F9FDCE light. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
--
-- Ships one colorscheme PER style ("thorn-forest" / "thorn-field"), and
-- registers colors_name as the same string, so theme-sync names them
-- separately and needs no colors_name pin.
return {
  "jpwol/thorn.nvim",
  name = "thorn",
  lazy = false,
  priority = 1000,
}
