-- spore (linhusp/spore.nvim) — theme-mode family. Dark-only mossy green
-- #101d1a; we wire the "softest" desaturation profile. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
--
-- Ships one colorscheme PER profile ("spore-softest" et al) and registers
-- colors_name as the same string, so theme-sync needs no colors_name pin.
return {
  "linhusp/spore.nvim",
  name = "spore",
  lazy = false,
  priority = 1000,
}
