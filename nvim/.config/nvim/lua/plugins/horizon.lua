-- horizon (akinsho/horizon.nvim) — theme-mode family.
-- Upstream's palette-light renamed its whole `syntax` table (amethyst/crimson/
-- jaffa/...), but theme.lua still reads the DARK names (apricot/cranberry/gray/
-- lavender/rosebud/tacao/turquoise) unconditionally through tint(), so light
-- mode crashes (E5113) and every syntax group would be nil. Backfill those keys
-- with the light hues the light `theme` table already carries. Dark untouched;
-- runtime patch because the upstream file is nomodifiable.
return {
  "akinsho/horizon.nvim",
  name = "horizon",
  lazy = false,
  priority = 1000,
  config = function()
    local ok, light = pcall(require, "horizon.palette-light")
    if ok and light.palette then
      light.palette.syntax = {
        apricot = "#DC3318", -- constant/number
        cranberry = "#DA103F", -- variable/field
        gray = "#333333", -- delimiter/operator
        lavender = "#8A31B9", -- keyword
        rosebud = "#F6661E", -- string/char
        tacao = "#F77D26", -- type/structure
        turquoise = "#1D8991", -- func/info
      }
    end
  end,
}
