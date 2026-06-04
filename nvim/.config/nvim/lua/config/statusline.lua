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
  venv = " ",
  unpushed = " ",
}

-- GENERIC_VENV_NAMES: when the venv basename is one of these, show the parent
-- directory name instead (more informative than ".venv").
local GENERIC_VENV_NAMES = { [".venv"] = true, ["venv"] = true, ["env"] = true }

-- Git ahead/behind cache.
--   Keys are git toplevel paths (strings).
--   Values are tables: { ahead = N, behind = N, no_upstream = bool, stranded = N|nil }
--     or nil when the directory is not a git repo.
local _git_cache = {}

-- In-flight guard: true while an async refresh is running for that toplevel.
local _git_inflight = {}

local function define_highlights()
  vim.api.nvim_set_hl(0, "StatuslineBranch", { fg = "#94e2d5", bg = "#313244", bold = true })
  -- Neutral/muted color for venv segment (context, not an alert).
  vim.api.nvim_set_hl(0, "StatuslineVenv", { fg = "#a6adc8", bg = "#313244" })
  -- Reuses DiagnosticWarn for the unpushed/no-upstream state — already catppuccin-consistent.
end

define_highlights()

vim.api.nvim_create_autocmd("ColorScheme", {
  group = vim.api.nvim_create_augroup("StatuslineHighlights", { clear = true }),
  callback = define_highlights,
})

-- venv_label: return the display name for the given VIRTUAL_ENV path.
-- Uses the basename unless it is generic, in which case the parent dir name is used.
local function venv_label(venv_path)
  local basename = vim.fn.fnamemodify(venv_path, ":t")
  if GENERIC_VENV_NAMES[basename] then
    return vim.fn.fnamemodify(venv_path, ":h:t")
  end
  return basename
end

-- git_refresh: asynchronously fetch ahead/behind for the given toplevel and
-- update the cache. Skips if a refresh is already in flight for this toplevel.
local function git_refresh(toplevel)
  if _git_inflight[toplevel] then
    return
  end
  _git_inflight[toplevel] = true

  vim.system(
    { "git", "-C", toplevel, "rev-list", "--count", "--left-right", "@{upstream}...HEAD" },
    { text = true },
    function(obj)
      if obj.code == 0 and obj.stdout and obj.stdout ~= "" then
        -- stdout is "behind\tahead\n"
        local behind_s, ahead_s = obj.stdout:match("^(%d+)%s+(%d+)")
        local behind = tonumber(behind_s) or 0
        local ahead = tonumber(ahead_s) or 0
        vim.schedule(function()
          _git_inflight[toplevel] = nil
          _git_cache[toplevel] = { ahead = ahead, behind = behind, no_upstream = false }
          vim.cmd.redrawstatus()
        end)
      else
        -- No upstream configured (exit 128) or other error.
        -- Try to count commits vs origin/HEAD to show stranded count.
        vim.system(
          { "git", "-C", toplevel, "rev-list", "--count", "origin/HEAD..HEAD" },
          { text = true },
          function(count_obj)
            vim.schedule(function()
              _git_inflight[toplevel] = nil
              local stranded = nil
              if count_obj.code == 0 and count_obj.stdout and count_obj.stdout ~= "" then
                stranded = tonumber(count_obj.stdout:match("%d+"))
              end
              _git_cache[toplevel] = { ahead = 0, behind = 0, no_upstream = true, stranded = stranded }
              vim.cmd.redrawstatus()
            end)
          end
        )
      end
    end
  )
end

-- git_toplevel_async: get the git toplevel for the given directory, then call
-- git_refresh. This runs git rev-parse asynchronously so the render path stays
-- pure Lua with zero subprocess calls.
local function git_toplevel_async(dir)
  vim.system({ "git", "-C", dir, "rev-parse", "--show-toplevel" }, { text = true }, function(obj)
    if obj.code ~= 0 then
      -- Not a git repo; cache a sentinel so we don't keep spawning.
      vim.schedule(function()
        _git_cache[dir] = false
      end)
      return
    end
    local toplevel = obj.stdout and obj.stdout:gsub("%s+$", "")
    if not toplevel or toplevel == "" then
      return
    end
    git_refresh(toplevel)
  end)
end

-- trigger_git_refresh: called from autocmds. Finds the buffer's directory,
-- skips non-file buffers and already-known non-repos.
local function trigger_git_refresh()
  local bufnr = vim.api.nvim_get_current_buf()
  local buftype = vim.bo[bufnr].buftype
  if buftype ~= "" then
    return
  end

  local bufname = vim.api.nvim_buf_get_name(bufnr)
  local dir
  if bufname ~= "" then
    dir = vim.fn.fnamemodify(bufname, ":p:h")
  else
    dir = vim.fn.getcwd()
  end

  -- If we already know this dir is not a git repo, skip.
  if _git_cache[dir] == false then
    return
  end

  git_toplevel_async(dir)
end

vim.api.nvim_create_autocmd({ "BufEnter", "FocusGained", "BufWritePost" }, {
  group = vim.api.nvim_create_augroup("StatuslineGitRefresh", { clear = true }),
  callback = trigger_git_refresh,
})

-- FugitiveChanged fires after fugitive push/pull/commit/checkout.
vim.api.nvim_create_autocmd("User", {
  pattern = "FugitiveChanged",
  group = vim.api.nvim_create_augroup("StatuslineGitFugitive", { clear = true }),
  callback = function()
    local bufnr = vim.api.nvim_get_current_buf()
    local bufname = vim.api.nvim_buf_get_name(bufnr)
    local dir = bufname ~= "" and vim.fn.fnamemodify(bufname, ":p:h") or vim.fn.getcwd()
    -- Invalidate cache so the next refresh fetches fresh data.
    _git_cache[dir] = nil
    trigger_git_refresh()
  end,
})

-- git_segment: read from cache and format. Zero subprocess calls.
-- Returns the cache entry or nil if not yet populated.
-- Also returns the toplevel key used so callers can check cache presence.
local function git_segment()
  local bufnr = vim.api.nvim_get_current_buf()
  local bufname = vim.api.nvim_buf_get_name(bufnr)
  local dir
  if bufname ~= "" then
    dir = vim.fn.fnamemodify(bufname, ":p:h")
  else
    dir = vim.fn.getcwd()
  end

  -- Walk the cache: the cache may be keyed by dir (sentinel false) or by toplevel.
  -- Check the dir sentinel first.
  if _git_cache[dir] == false then
    return nil
  end

  -- Search for a toplevel that is a prefix of dir.
  local entry = nil
  for key, val in pairs(_git_cache) do
    if val and type(val) == "table" then
      if dir == key or dir:sub(1, #key + 1) == key .. "/" then
        entry = val
        break
      end
    end
  end

  if not entry then
    return nil
  end

  local parts = {}

  if entry.no_upstream then
    -- Branch has never been pushed — distinct warning state.
    if entry.stranded and entry.stranded > 0 then
      parts[#parts + 1] = "%#DiagnosticWarn#" .. ICONS.unpushed .. entry.stranded .. " unpushed%*"
    else
      parts[#parts + 1] = "%#DiagnosticWarn#" .. ICONS.unpushed .. "unpushed%*"
    end
    return table.concat(parts)
  end

  if entry.ahead == 0 and entry.behind == 0 then
    return nil
  end

  if entry.ahead > 0 then
    parts[#parts + 1] = "%#DiagnosticWarn#↑" .. entry.ahead .. "%*"
  end
  if entry.behind > 0 then
    parts[#parts + 1] = "%#DiagnosticHint#↓" .. entry.behind .. "%*"
  end

  return table.concat(parts, " ")
end

function _G.Statusline_render()
  local parts = {}

  local branch = vim.b.gitsigns_head
  if branch and branch ~= "" then
    parts[#parts + 1] = "%#StatuslineBranch# " .. ICONS.branch .. branch .. " %*"
  end

  parts[#parts + 1] = "%="

  -- Python venv segment: cheap env-var read, shown only in python buffers.
  if vim.bo.filetype == "python" then
    local venv = os.getenv("VIRTUAL_ENV")
    if venv and venv ~= "" then
      parts[#parts + 1] = "%#StatuslineVenv# " .. ICONS.venv .. venv_label(venv) .. " %*"
    end
  end

  local counts = vim.diagnostic.count(0)
  local errors = counts[ERROR] or 0
  local warns = counts[WARN] or 0

  if errors > 0 then
    parts[#parts + 1] = "%#DiagnosticError#" .. ICONS.error .. errors .. " %*"
  end

  if warns > 0 then
    parts[#parts + 1] = "%#DiagnosticWarn#" .. ICONS.warn .. warns .. " %*"
  end

  local git = git_segment()
  if git then
    parts[#parts + 1] = git .. " "
  end

  return table.concat(parts)
end

vim.o.statusline = "%!v:lua.Statusline_render()"

return M
