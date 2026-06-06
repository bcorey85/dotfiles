-- Tmux pane-zoom helpers, deduplicated from the copy-pasted zoom dance that
-- previously lived separately in diffview, neogit, and dap. All functions are
-- TMUX-guarded internally, so callers do not need their own `vim.env.TMUX`
-- checks — just call zoom/unzoom directly.
local M = {}

local function in_tmux()
  return vim.env.TMUX ~= nil
end

-- True only when inside tmux AND the current pane is zoomed.
function M.is_zoomed()
  if not in_tmux() then
    return false
  end
  local out = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
  return out == "1"
end

-- Zoom the current pane if not already zoomed (idempotent).
function M.zoom()
  if in_tmux() and not M.is_zoomed() then
    vim.fn.system("tmux resize-pane -Z")
  end
end

-- Un-zoom the current pane if currently zoomed (idempotent).
function M.unzoom()
  if in_tmux() and M.is_zoomed() then
    vim.fn.system("tmux resize-pane -Z")
  end
end

return M
