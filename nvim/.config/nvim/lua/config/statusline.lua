-- Hand-rolled minimal statusline.
--
-- Design: the statusline surfaces exactly three signals — the current git
-- branch, LSP progress while work is in flight, and a diagnostic count.
-- Everything else that lualine/mini.statusline used to show has a better,
-- less noisy home:
--   mode       → cursor shape (normal=block, insert=bar, replace=underline)
--   filename   → winbar (cwd-relative path breadcrumb + modified flag)
--   line/col   → relative line numbers + ruler in the gutter
--   diff +/-/~ → gitsigns sign column (per-line, right where the change is)

local M = {}

local ERROR = vim.diagnostic.severity.ERROR
local WARN = vim.diagnostic.severity.WARN

-- Populated with standard Nerd Fonts. Adjust if using a different font set.
local ICONS = {
  branch = " ",
  error = " ",
  warn = " ",
  venv = " ",
  unpushed = "󰶣 ",
  search = "\xF3\xB0\x8D\x89 ",
}

local GENERIC_VENV_NAMES = { [".venv"] = true, ["venv"] = true, ["env"] = true }

-- Git lookups: Split into a toplevel state cache and a dir-to-toplevel map
-- to achieve instant O(1) lookups during statusline rendering.
local _git_cache = {}
local _dir_to_toplevel = {}
local _git_inflight = {}

local function define_highlights()
  vim.api.nvim_set_hl(0, "StatuslineBranch", { fg = "#94e2d5", bg = "#313244", bold = true })
  vim.api.nvim_set_hl(0, "StatuslineVenv", { fg = "#a6adc8", bg = "#313244" })
  vim.api.nvim_set_hl(0, "StatuslineRecording", { fg = "#f38ba8", bold = true })

  -- HIGH VISIBILITY: Inverted block badge for modified files (Dark Crust text on Bright Red background)
  vim.api.nvim_set_hl(0, "StatuslineModified", { fg = "#11111b", bg = "#f38ba8", bold = true })
end

define_highlights()

vim.api.nvim_create_autocmd("ColorScheme", {
  group = vim.api.nvim_create_augroup("StatuslineHighlights", { clear = true }),
  callback = define_highlights,
})

local _lsp_progress = nil
local _lsp_progress_token = 0

vim.api.nvim_create_autocmd("LspProgress", {
  group = vim.api.nvim_create_augroup("StatuslineLspProgress", { clear = true }),
  callback = function(ev)
    local value = ev.data and ev.data.params and ev.data.params.value
    if not value then
      return
    end

    local client = vim.lsp.get_client_by_id(ev.data.client_id)
    local safe = function(s)
      return (s or ""):gsub("%%", "%%%%")
    end
    local client_name = safe(client and client.name or "lsp")
    local title = safe(value.title)
    local msg = safe(value.message)

    if value.kind == "end" then
      local token = _lsp_progress_token + 1
      _lsp_progress_token = token
      local label = client_name .. ": " .. title
      if msg ~= "" then
        label = label .. " " .. msg
      end
      _lsp_progress = label
      vim.cmd.redrawstatus()
      vim.defer_fn(function()
        if _lsp_progress_token == token then
          _lsp_progress = nil
          vim.cmd.redrawstatus()
        end
      end, 1500)
      return
    end

    local label = client_name .. ": " .. title
    if msg ~= "" then
      label = label .. " " .. msg
    end
    if value.percentage then
      label = label .. " " .. tostring(value.percentage) .. "%%"
    end
    _lsp_progress = label
    _lsp_progress_token = _lsp_progress_token + 1
    vim.cmd.redrawstatus()
  end,
})

local function venv_label(venv_path)
  local basename = vim.fn.fnamemodify(venv_path, ":t")
  if GENERIC_VENV_NAMES[basename] then
    return vim.fn.fnamemodify(venv_path, ":h:t")
  end
  return basename
end

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
        local behind_s, ahead_s = obj.stdout:match("^(%d+)%s+(%d+)")
        local behind = tonumber(behind_s) or 0
        local ahead = tonumber(ahead_s) or 0
        vim.schedule(function()
          _git_inflight[toplevel] = nil
          _git_cache[toplevel] = { ahead = ahead, behind = behind, no_upstream = false }
          vim.cmd.redrawstatus()
        end)
      else
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

local function git_toplevel_async(dir)
  vim.system({ "git", "-C", dir, "rev-parse", "--show-toplevel" }, { text = true }, function(obj)
    if obj.code ~= 0 then
      vim.schedule(function()
        _dir_to_toplevel[dir] = false
      end)
      return
    end
    local toplevel = obj.stdout and obj.stdout:gsub("%s+$", "")
    if not toplevel or toplevel == "" then
      return
    end

    vim.schedule(function()
      _dir_to_toplevel[dir] = toplevel
      git_refresh(toplevel)
    end)
  end)
end

local function trigger_git_refresh()
  local bufnr = vim.api.nvim_get_current_buf()
  if vim.bo[bufnr].buftype ~= "" then
    return
  end

  local bufname = vim.api.nvim_buf_get_name(bufnr)
  local dir = bufname ~= "" and vim.fn.fnamemodify(bufname, ":p:h") or vim.fn.getcwd()

  if _dir_to_toplevel[dir] == false then
    return
  end

  git_toplevel_async(dir)
end

vim.api.nvim_create_autocmd({ "BufEnter", "FocusGained", "BufWritePost" }, {
  group = vim.api.nvim_create_augroup("StatuslineGitRefresh", { clear = true }),
  callback = trigger_git_refresh,
})

-- Invalidate the toplevel cache and re-run the async refresh after any
-- fugitive Git command completes (e.g. commit, push, pull), so the
-- unpushed-count badge stays accurate without a full BufEnter cycle.
vim.api.nvim_create_autocmd("User", {
  pattern = "FugitiveChanged",
  group = vim.api.nvim_create_augroup("StatuslineGitFugitive", { clear = true }),
  callback = function()
    local bufnr = vim.api.nvim_get_current_buf()
    local bufname = vim.api.nvim_buf_get_name(bufnr)
    local dir = bufname ~= "" and vim.fn.fnamemodify(bufname, ":p:h") or vim.fn.getcwd()
    _dir_to_toplevel[dir] = nil
    trigger_git_refresh()
  end,
})

local function git_segment()
  local bufnr = vim.api.nvim_get_current_buf()
  local bufname = vim.api.nvim_buf_get_name(bufnr)
  local dir = bufname ~= "" and vim.fn.fnamemodify(bufname, ":p:h") or vim.fn.getcwd()

  local toplevel = _dir_to_toplevel[dir]
  if toplevel == false or not toplevel then
    return nil
  end

  local entry = _git_cache[toplevel]
  if not entry then
    return nil
  end

  local parts = {}

  if entry.no_upstream then
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

-- Search match position (current/total), reclaiming the native [n/N] counter
-- that cmdheight=0 hides. Gated on vim.v.hlsearch so it only appears while a
-- search is highlighted (the <esc>→:noh map clears it). recompute=true keeps
-- `current` accurate as the cursor moves through matches with n/N.
local function search_segment()
  if vim.v.hlsearch == 0 then
    return nil
  end
  local ok, sc = pcall(vim.fn.searchcount, { recompute = true, maxcount = 999, timeout = 250 })
  if not ok or type(sc) ~= "table" or (sc.total or 0) == 0 then
    return nil
  end
  local label
  if sc.incomplete == 1 then
    -- searchcount timed out before finishing the count
    label = "?/?"
  elseif sc.incomplete == 2 then
    -- more matches than maxcount; show the cap with a trailing +
    label = sc.current .. "/" .. sc.maxcount .. "+"
  else
    label = sc.current .. "/" .. sc.total
  end
  return "%#StatuslineVenv# " .. ICONS.search .. label .. " %*"
end

local function project_segment()
  -- Use the toplevel already resolved by the async git cache; fall back to cwd.
  local bufnr = vim.api.nvim_get_current_buf()
  local bufname = vim.api.nvim_buf_get_name(bufnr)
  local dir = bufname ~= "" and vim.fn.fnamemodify(bufname, ":p:h") or vim.fn.getcwd()
  local toplevel = _dir_to_toplevel[dir]
  if toplevel and toplevel ~= false and toplevel ~= "" then
    return vim.fs.basename(toplevel)
  end
  return vim.fs.basename(vim.fn.getcwd())
end

local function readonly_segment()
  if vim.bo.readonly or not vim.bo.modifiable then
    -- Added a leading space before the icon so it centers perfectly in the block
    return "%#StatuslineModified#  %*"
  end
  return nil
end

vim.api.nvim_create_autocmd("RecordingEnter", {
  group = vim.api.nvim_create_augroup("StatuslineRecording", { clear = true }),
  callback = function()
    vim.cmd.redrawstatus()
  end,
})

vim.api.nvim_create_autocmd("RecordingLeave", {
  group = "StatuslineRecording",
  callback = function()
    vim.schedule(function()
      vim.cmd.redrawstatus()
    end)
  end,
})

local function recording_segment()
  local reg = vim.fn.reg_recording()
  return reg ~= "" and ("%#StatuslineRecording#⏺ REC @" .. reg .. "%*") or nil
end

function _G.Statusline_render()
  local parts = {}

  local rec = recording_segment()
  if rec then
    parts[#parts + 1] = rec .. " "
  end

  local project = project_segment()
  if project then
    parts[#parts + 1] = "%#StatuslineVenv# " .. project .. " %*"
  end

  -- gitsigns sets b:gitsigns_head to the current branch short name whenever it
  -- attaches to a buffer. Falls back to nil for non-git buffers (dashboard, help).
  local branch = vim.b.gitsigns_head
  if branch and branch ~= "" then
    parts[#parts + 1] = "%#StatuslineBranch# " .. ICONS.branch .. branch .. " %*"
  end

  local ro = readonly_segment()
  if ro then
    parts[#parts + 1] = ro
  end

  -- Transient readouts live in the empty middle so they never jitter the
  -- right-anchored diagnostics/git: search count, then the native showcmd via
  -- %S (rendered raw so it occupies nothing when there's no pending command).
  local search = search_segment()
  if search then
    parts[#parts + 1] = search .. " "
  end
  parts[#parts + 1] = "%S "

  parts[#parts + 1] = "%="

  if _lsp_progress and _lsp_progress ~= "" then
    parts[#parts + 1] = "%#StatuslineVenv# " .. _lsp_progress .. " %*"
  end

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
