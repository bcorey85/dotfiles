-- edge (sainnhe/edge) — theme-mode family, aura style (the dimmed style).
-- OneDark-genre vivid on dimmed #2b2d37 dark / #fafafa light. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before config.lazy.lua's
-- theme-sync.start().
--
-- One colorscheme "edge" follows vim.o.background, so colors_name is pinned
-- like vitesse's. theme-sync sets edge_style=aura via pre(); the
-- ghostty/hunk/herdr/starship palettes all encode aura-style chrome
-- (bg0 #2b2d37). No orange
-- slot in the palette, so yellow doubles for peach.
return {
  "sainnhe/edge",
  name = "edge",
  lazy = false,
  priority = 1000,
}
