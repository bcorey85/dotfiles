-- rose-pine — "all natural pine, faux fur and a bit of soho vibes". Ships three
-- variants as separate colorschemes (main/moon/dawn) that all register
-- colors_name = "rose-pine", so theme-sync pins the pair explicitly (main dark,
-- dawn light) and matches the override guard on colors_name.
-- Benched: loads via the theme switcher (theme-mode use rose-pine).
return {
  "rose-pine/neovim",
  name = "rose-pine",
  lazy = true,
}
