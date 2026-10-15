-- dredge for lualine, loaded by theme = "auto". One flat bar on the statusline
-- ground and no mode colours: the bar shows no mode. Built from the live
-- StatusLine groups, so light and dark follow the colorscheme.
local function hl(name)
  local group = vim.api.nvim_get_hl(0, { name = name, link = false })
  return { fg = string.format("#%06x", group.fg), bg = string.format("#%06x", group.bg) }
end

local active = hl("StatusLine")
local inactive = hl("StatusLineNC")
local muted = { fg = inactive.fg, bg = active.bg }

return {
  normal = { a = active, b = muted, c = active },
  inactive = { a = inactive, b = inactive, c = inactive },
}
