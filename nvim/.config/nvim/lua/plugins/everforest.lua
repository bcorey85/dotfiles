-- everforest (sainnhe/everforest) — theme-mode family, medium background.
-- Green-grey forest tones on #2d353b dark / #fdf6e3 light. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before config.lazy.lua's
-- theme-sync.start().
--
-- One colorscheme "everforest" follows vim.o.background and sets colors_name
-- "everforest" in both modes, so theme-sync pins it.
return {
  "sainnhe/everforest",
  name = "everforest",
  lazy = false,
  priority = 1000,
}
