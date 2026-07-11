-- solarized.nvim — Ethan Schoonover's Solarized. The plugin also carries a
-- selenized palette, but both load through the SAME `:colorscheme solarized`
-- and differ only by a setup() option, so theme-sync pins ours in the family's
-- `pre` hook (palette = "solarized") rather than relying on the default.
-- Light/dark comes from vim.o.background, like the other one-scheme families.
-- Benched: loads via the theme switcher (theme-mode use solarized).
return {
  "maxmx03/solarized.nvim",
  lazy = true,
}
