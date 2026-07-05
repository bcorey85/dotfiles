-- theme-sync — keep nvim's colorscheme background in sync with the shared
-- light/dark state written by the `theme-mode` script (see
-- scripts/.local/bin/theme-mode).
--
-- Design: one state file (~/.cache/theme-mode) holds "dark" or "light". tmux
-- and nvim both read it. nvim polls the file via libuv fs_poll (~1s) so a
-- toggle from tmux (prefix t) flips every running instance, focused or not,
-- with no sockets or lifecycle to manage. <leader>ut shells out to the same
-- script, so a toggle from nvim flips tmux too — one source of truth, both ways.
--
-- nightfox.nvim doesn't auto-switch on vim.o.background — it ships separate
-- colorscheme names per variant, so each mode maps to its own name here.

local M = {}

local STATE_FILE = vim.env.HOME .. "/.cache/theme-mode"
local COLORSCHEMES = { dark = "terafox", light = "dayfox" }

local applied ---@type string|nil  last mode we set, to skip redundant reloads

-- Normalize any input to "dark" (the default) or "light".
local function normalize(mode)
  return mode == "light" and "light" or "dark"
end

-- Read the mode from the state file; default to dark if missing/garbage.
function M.read_mode()
  local f = io.open(STATE_FILE, "r")
  if not f then
    return "dark"
  end
  local raw = f:read("l") or ""
  f:close()
  return normalize(raw:gsub("%s+", ""))
end

-- Apply a mode by setting background and re-running :colorscheme. Skips the
-- reload if it's already active (a colorscheme reload clears user highlights
-- and re-runs the theme build), unless `force` is set (used for the initial
-- apply).
function M.apply(mode, force)
  mode = normalize(mode)
  if not force and mode == applied then
    return
  end
  applied = mode
  vim.o.background = mode
  vim.cmd.colorscheme(COLORSCHEMES[mode])
end

function M.apply_from_file(force)
  M.apply(M.read_mode(), force)
end

local poll -- libuv fs_poll handle, created lazily in start()

-- Apply the current mode now and start watching the state file for changes.
function M.start()
  -- Ensure the file exists so fs_poll has a target (the script also creates it).
  if not vim.uv.fs_stat(STATE_FILE) then
    local f = io.open(STATE_FILE, "w")
    if f then
      f:write("dark\n")
      f:close()
    end
  end

  M.apply_from_file(true)

  if poll then
    return
  end
  poll = vim.uv.new_fs_poll()
  if poll then
    -- 1s cadence: imperceptible for a manual toggle, negligible overhead.
    poll:start(
      STATE_FILE,
      1000,
      vim.schedule_wrap(function()
        M.apply_from_file(false)
      end)
    )
  end
end

return M
