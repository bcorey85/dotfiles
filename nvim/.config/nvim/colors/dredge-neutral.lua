-- Trial, nvim only: dredge's dark palette with monoglow's neutral ground and
-- grey ladder. Hues are dredge's own. `:colorscheme dredge-neutral`.
local swaps = {
  ["#191f25"] = "#1c1c1c", -- bg
  ["#12181e"] = "#161616", -- bg_dark
  ["#262c33"] = "#292929", -- bg_line
  ["#1e242b"] = "#222222", -- bg_cursor
  ["#353b42"] = "#383838", -- bg_sel
  ["#3b4249"] = "#404040", -- bg_visual
  ["#41484f"] = "#454545", -- border
  ["#454c53"] = "#494949", -- nontext
  ["#9599a0"] = "#707070", -- linenr
  ["#a5a9b0"] = "#a1a1a1", -- muted
  ["#bec3cb"] = "#b1b1b1", -- comment
  ["#989ea4"] = "#a1a1a1", -- punct
  ["#95a5b5"] = "#949494", -- kw
  ["#c1cfdc"] = "#c0c0c0", -- fg
  ["#d9e0eb"] = "#d1d1d1", -- fg_bright
  ["#d7dfe9"] = "#c0c0c0", -- term white
}

-- dredge-moody passes its hue swaps here.
for from, to in pairs(vim.g.dredge_trial_swaps or {}) do
  swaps[from] = to
end
vim.g.dredge_trial_swaps = nil

local files =vim.api.nvim_get_runtime_file("colors/dredge.lua", false)
if #files == 0 then
  error("dredge-neutral: colors/dredge.lua is not on the runtimepath")
end
local source = table.concat(vim.fn.readfile(files[1]), "\n")
source = source:gsub("#%x%x%x%x%x%x", function(hex)
  return swaps[hex:lower()] or hex
end)

vim.o.background = "dark"
local chunk = assert(loadstring(source, "dredge-neutral"))
chunk()
vim.g.colors_name = "dredge-neutral"
