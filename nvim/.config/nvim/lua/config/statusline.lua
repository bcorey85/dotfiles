-- Hand-rolled minimal statusline.
--
-- Design: the statusline surfaces exactly two signals — the current git branch
-- and a diagnostic count. Everything else that lualine/mini.statusline used to
-- show has a better, less noisy home:
--   mode       → cursor shape (normal=block, insert=bar, replace=underline)
--   filename   → breadcrumbs winbar (always visible, full path context)
--   line/col   → relative line numbers + ruler in the gutter
--   diff +/-/~ → gitsigns sign column (per-line, right where the change is)
-- Diagnostics are kept because nothing else aggregates them in one place.
-- Mode, location, search count, and fileinfo are intentionally omitted.
--
-- laststatus=3 (global statusline) is set in config/options.lua:18 and is
-- unaffected by this module.

local M = {}

local ERROR = vim.diagnostic.severity.ERROR
local WARN = vim.diagnostic.severity.WARN

local ICONS = {
  branch = " ",
  error = " ",
  warn = " ",
}

local function define_highlights()
  vim.api.nvim_set_hl(0, "StatuslineBranch", { fg = "#94e2d5", bg = "#313244", bold = true })
end

define_highlights()

vim.api.nvim_create_autocmd("ColorScheme", {
  group = vim.api.nvim_create_augroup("StatuslineHighlights", { clear = true }),
  callback = define_highlights,
})

function _G.Statusline_render()
  local parts = {}

  local branch = vim.b.gitsigns_head
  if branch and branch ~= "" then
    parts[#parts + 1] = "%#StatuslineBranch# " .. ICONS.branch .. branch .. " %#Normal#"
  end

  parts[#parts + 1] = "%="

  local counts = vim.diagnostic.count(0)
  local errors = counts[ERROR] or 0
  local warns = counts[WARN] or 0

  if errors > 0 then
    parts[#parts + 1] = "%#DiagnosticError#" .. ICONS.error .. errors .. " %#Normal#"
  end

  if warns > 0 then
    parts[#parts + 1] = "%#DiagnosticWarn#" .. ICONS.warn .. warns .. " %#Normal#"
  end

  return table.concat(parts)
end

vim.o.statusline = "%!v:lua.Statusline_render()"

return M
