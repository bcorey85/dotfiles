-- vitesse (bcorey85/vitesse.nvim, a pure-Lua port of antfu's Vitesse) — theme-mode
-- family. One colorscheme "vitesse" follows vim.o.background and sets colors_name
-- "vitesse" in both modes, so theme-sync pins it. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before theme-sync.start().
return {
  "bcorey85/vitesse.nvim",
  name = "vitesse",
  lazy = false,
  priority = 1000,
  opts = { italic_comments = false },
}
