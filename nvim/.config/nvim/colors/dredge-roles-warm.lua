-- dredge-roles-warm — on trial: dredge-roles on a warm-neutral ground. Dark only; light is
-- dredge-roles unchanged. Each step keeps dredge's lightness, at OKLCH C 0.006, h 90.

vim.g.dredge_overrides = {
  dark = {
    bg = "#181714",
    bg_dark = "#11100d",
    bg_line = "#252421",
    bg_cursor = "#1e1d1a",
    bg_sel = "#302f2b",
    bg_visual = "#363531",
    border = "#3c3b37",
    nontext = "#403f3c",
  },
}
vim.cmd.runtime("colors/dredge-roles.lua")
vim.g.dredge_overrides = nil
vim.g.colors_name = "dredge-roles-warm"
