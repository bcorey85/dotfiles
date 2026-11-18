-- Trial, nvim only: dredge-neutral with each syntax hue darker (OKLCH L -0.06)
-- and a tenth less saturated. `:colorscheme dredge-moody`.
vim.g.dredge_trial_swaps = {
  ["#9ca4f1"] = "#8b92d6", -- fn
  ["#9eb34a"] = "#8d9f43", -- type
  ["#5bb2e7"] = "#529ecd", -- builtin
  ["#f0925f"] = "#d68356", -- param
  ["#f78d83"] = "#dc7f76", -- attr
  ["#c5a769"] = "#af955f", -- remark
  ["#5ab9b0"] = "#51a49c", -- str
  ["#f38ba5"] = "#d97d94", -- const
}
vim.cmd.runtime("colors/dredge-neutral.lua")
vim.g.colors_name = "dredge-moody"
