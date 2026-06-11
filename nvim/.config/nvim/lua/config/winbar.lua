-- Hand-rolled winbar: a cwd-relative path breadcrumb with a file icon and a
-- modified flag. Replaces barbecue — we want the file's *location*, not the
-- LSP class/method symbols barbecue layered on top. The filename used to live
-- on the statusline's left; it now lives here.
--
-- Why literal strings instead of a `%!` expression (like the statusline uses):
-- a `%!` winbar is always evaluated against the genuinely-current window, so
-- every split would render the focused file's path. We instead compute a plain
-- string per window and assign it to that window's local 'winbar', refreshing
-- via autocmds. (The `%` chars in the result still get winbar-interpreted, so
-- path segments are escaped below.)

-- Resolve nvim-web-devicons lazily: at the time this module is sourced (before
-- pack.setup runs) the plugin isn't on the runtimepath yet, so a top-level
-- require would fail and cache a permanent miss. Retry on each call until it
-- loads, then cache the module. (The "nvim-web-devicons" require is satisfied
-- by MiniIcons.mock_nvim_web_devicons(), called in mini-icons.lua's setup().)
local _devicons
local function get_devicons()
  if _devicons then
    return _devicons
  end
  local ok, mod = pcall(require, "nvim-web-devicons")
  if ok then
    _devicons = mod
  end
  return _devicons
end

-- Thin powerline chevron (U+E0B1) as the breadcrumb separator.
local SEP = " \xEE\x82\xB1 "

local function define_highlights()
  -- bg = NONE so segments inherit the window's Winbar/Normal background.
  vim.api.nvim_set_hl(0, "WinbarPath", { fg = "#6c7086", bg = "NONE" })
  vim.api.nvim_set_hl(0, "WinbarFile", { fg = "#cdd6f4", bg = "NONE", bold = true })
  vim.api.nvim_set_hl(0, "WinbarModified", { fg = "#f38ba8", bg = "NONE", bold = true })
end

define_highlights()

vim.api.nvim_create_autocmd("ColorScheme", {
  group = vim.api.nvim_create_augroup("WinbarHighlights", { clear = true }),
  callback = define_highlights,
})

-- Escape `%` so filenames/dirs containing it aren't read as winbar items.
local function esc(s)
  return (s:gsub("%%", "%%%%"))
end

-- A window gets a winbar only if it's a normal, non-floating window holding a
-- real file buffer. Special buffers (oil, mini.pick, quickfix, help, terminals)
-- and floats stay bare.
local function eligible(win)
  if vim.api.nvim_win_get_config(win).relative ~= "" then
    return false
  end
  local buf = vim.api.nvim_win_get_buf(win)
  if vim.bo[buf].buftype ~= "" then
    return false
  end
  return vim.api.nvim_buf_get_name(buf) ~= ""
end

-- Build the breadcrumb for the *current* window (correct here because the
-- update() callbacks below run with the target window current).
local function render()
  local path = vim.fn.expand("%:.")
  if path == "" then
    return ""
  end

  local parts = vim.split(path, "/", { plain = true })
  local filename = table.remove(parts)

  local segments = {}
  for _, dir in ipairs(parts) do
    segments[#segments + 1] = "%#WinbarPath#" .. esc(dir) .. "%*"
  end

  local icon_str = ""
  local devicons = get_devicons()
  if devicons then
    local icon, icon_hl = devicons.get_icon(filename, vim.fn.fnamemodify(filename, ":e"), { default = true })
    if icon then
      icon_str = "%#" .. (icon_hl or "WinbarFile") .. "#" .. icon .. "%* "
    end
  end

  local mod = vim.bo.modified and " %#WinbarModified#●%*" or ""
  segments[#segments + 1] = icon_str .. "%#WinbarFile#" .. esc(filename) .. "%*" .. mod

  return " " .. table.concat(segments, "%#WinbarPath#" .. SEP .. "%*")
end

local function update()
  local win = vim.api.nvim_get_current_win()
  vim.wo[win].winbar = eligible(win) and render() or ""
end

-- BufModifiedSet keeps the ● in sync the moment &modified flips; the rest catch
-- a window changing which buffer it holds.
vim.api.nvim_create_autocmd({ "BufWinEnter", "WinEnter", "BufEnter", "BufWritePost", "BufModifiedSet", "FileType" }, {
  group = vim.api.nvim_create_augroup("Winbar", { clear = true }),
  callback = update,
})
