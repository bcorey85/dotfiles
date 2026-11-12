-- hybrid-light — theme-mode family "hybrid" (light). hybrid.nvim builds every group from
-- one palette table, so this runs the plugin's own loader over a light palette and then
-- puts the dark one back. The hues are Tomorrow's, darkened until each holds 4.5:1 as
-- text on white: the plugin's "bright" tier is the strongest, so here it is the darkest.

local colors = require("hybrid.colors")
local dark_palette = colors.palette

-- stylua: ignore
colors.palette = {
  bright_black   = "#d6d6d6", black   = "#ffffff", dull_black   = "#efefef",
  bright_white   = "#1d1f21", white   = "#4d4d4c", dull_white   = "#8e908c",
  bright_red     = "#a81e1f", red     = "#c82829", dull_red     = "#c14545",
  bright_green   = "#4f6600", green   = "#5f7700", dull_green   = "#66800f",
  bright_yellow  = "#7a5e00", yellow  = "#8f6f00", dull_yellow  = "#b85a00",
  bright_blue    = "#2f5f9f", blue    = "#4271ae", dull_blue    = "#4a74aa",
  bright_magenta = "#7446a0", magenta = "#8959a8", dull_magenta = "#9069ab",
  bright_cyan    = "#1f7178", cyan    = "#2c7d83", dull_cyan    = "#3d858a",
}

vim.o.background = "light"
local loaded, problem = pcall(require("hybrid").load)
colors.palette = dark_palette
if not loaded then
  error(problem, 0)
end
vim.g.colors_name = "hybrid-light"
