-- one — olimorris/onedarkpro.nvim, Atom's One Dark/One Light. Ships onedark
-- and onelight as separate colorschemes (each compiles its own colors_name);
-- theme-sync pins the pair. Cooler, sharper cousin of the doom-one family.
-- Loads via the theme switcher (theme-mode use one).
--
-- onelight is recolored for readability. Stock One Light is tuned for a pure
-- #fafafa bg and its warm syntax hues are brutally low-contrast anywhere —
-- orange 2.0:1, yellow 1.7:1, cyan 2.0:1 (WCAG needs 4.5). We tone the glary
-- near-white bg down to #eaeaea and darken every syntax hue to clear ~5:1
-- against it (body fg ~6.7:1). Warm colors go deep/burnt because that is the
-- only way orange/yellow read on a light background.
--
-- These override onelight's `palette` table, which IS its `default_colors`
-- object (themes/onelight.lua) — the override mutates it in place *before* the
-- `generated` closure derives cursorline/selection/float_bg + git/diff washes
-- via darken/blend(bg, …), so bg (and the hues) cascade to every derived
-- surface. Keep the bg in sync with ghostty/tmux one-light (#eaeaea). onedark
-- (dark mode) is untouched — this is namespaced to onelight. Comment contrast
-- is handled in theme-sync's `one` fixup (it also sets italic).
return {
  "olimorris/onedarkpro.nvim",
  lazy = true,
  priority = 1000,
  opts = {
    colors = {
      onelight = {
        bg = "#eaeaea", -- toned down from stock #fafafa (too glary)
        fg = "#505050", -- body text, 6.70:1 (stock #6a6a6a was 4.50:1)
        red = "#c31725", -- 5.03:1  (stock #e05661, 3.08:1)
        orange = "#955103", -- 5.05:1  (stock #ee9025, 2.02:1 — the "brutal" one)
        yellow = "#865903", -- 5.07:1  (stock #eea825, 1.70:1)
        green = "#0e7306", -- 5.03:1  (stock #1da912, 2.59:1)
        cyan = "#206c76", -- 5.03:1  (stock #56b6c2, 1.97:1)
        blue = "#056995", -- 5.04:1  (stock #118dc3, 3.10:1)
        purple = "#7942cc", -- 5.04:1  (stock #9a77cf, 2.95:1)
      },
    },
  },
}
