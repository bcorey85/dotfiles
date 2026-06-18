-- String helpers shared by the hand-rolled statusline/winbar modules.
local M = {}

-- Escape `%` so a string embedded in a statusline/winbar expression isn't read
-- as a status item — e.g. filenames or LSP messages that contain a literal %.
-- nil-safe so callers can pass a possibly-absent field directly.
function M.escape_pct(s)
  return ((s or ""):gsub("%%", "%%%%"))
end

return M
