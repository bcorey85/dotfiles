-- Async git toplevel + ahead/behind-upstream cache, shared by the statusline's
-- project and ahead/behind segments. Kept separate from util/git.lua (which is
-- synchronous, for on-demand callers) because this maintains a redraw-driving
-- cache across the whole session.
local M = {}

local _dir_to_toplevel = {}
local _status_cache = {}
local _inflight = {}

function M.current_dir()
  local bufname = vim.api.nvim_buf_get_name(vim.api.nvim_get_current_buf())
  return bufname ~= "" and vim.fn.fnamemodify(bufname, ":p:h") or vim.fn.getcwd()
end

local function refresh(toplevel)
  if _inflight[toplevel] then
    return
  end
  _inflight[toplevel] = true

  vim.system(
    { "git", "-C", toplevel, "rev-list", "--count", "--left-right", "@{upstream}...HEAD" },
    { text = true },
    function(obj)
      if obj.code == 0 and obj.stdout and obj.stdout ~= "" then
        local behind_s, ahead_s = obj.stdout:match("^(%d+)%s+(%d+)")
        vim.schedule(function()
          _inflight[toplevel] = nil
          _status_cache[toplevel] =
            { ahead = tonumber(ahead_s) or 0, behind = tonumber(behind_s) or 0, no_upstream = false }
          require("lualine").refresh()
        end)
      else
        vim.system(
          { "git", "-C", toplevel, "rev-list", "--count", "origin/HEAD..HEAD" },
          { text = true },
          function(count_obj)
            vim.schedule(function()
              _inflight[toplevel] = nil
              local stranded = nil
              if count_obj.code == 0 and count_obj.stdout and count_obj.stdout ~= "" then
                stranded = tonumber(count_obj.stdout:match("%d+"))
              end
              _status_cache[toplevel] = { ahead = 0, behind = 0, no_upstream = true, stranded = stranded }
              require("lualine").refresh()
            end)
          end
        )
      end
    end
  )
end

local function toplevel_async(dir)
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
      refresh(toplevel)
    end)
  end)
end

-- Trigger (re)resolution for the current buffer's directory. Safe to call on
-- every redraw-adjacent event: cache + inflight guards make repeats free.
function M.trigger()
  if not require("util.buf").is_file() then
    return
  end

  local dir = M.current_dir()
  local cached = _dir_to_toplevel[dir]
  if cached == false then
    return
  end
  if cached then
    refresh(cached)
    return
  end
  toplevel_async(dir)
end

-- Toplevel for the current buffer's dir, or nil (not yet resolved / not a repo).
function M.toplevel()
  local t = _dir_to_toplevel[M.current_dir()]
  return (t and t ~= false) and t or nil
end

-- { ahead=, behind=, no_upstream=, stranded= } for the current toplevel, or nil.
function M.status()
  local toplevel = M.toplevel()
  return toplevel and _status_cache[toplevel] or nil
end

vim.api.nvim_create_autocmd({ "BufEnter", "FocusGained", "BufWritePost" }, {
  group = vim.api.nvim_create_augroup("GitStatusRefresh", { clear = true }),
  callback = M.trigger,
})

-- Invalidate the toplevel cache and re-run the async refresh after any neogit
-- operation completes (commit, push, pull, fetch, branch, rebase, merge,
-- stash, reset, checkout), so the unpushed-count badge stays accurate without
-- a full BufEnter cycle. NeogitStatusRefreshed is deliberately excluded — it
-- fires on the 1s filewatcher poll and would spam refreshes.
vim.api.nvim_create_autocmd("User", {
  pattern = {
    "NeogitCommitComplete",
    "NeogitPushComplete",
    "NeogitPullComplete",
    "NeogitFetchComplete",
    "NeogitRebase",
    "NeogitMerge",
    "NeogitReset",
    "NeogitBranchCreate",
    "NeogitBranchDelete",
    "NeogitBranchCheckout",
    "NeogitBranchRename",
    "NeogitStash",
    "NeogitTagCreate",
    "NeogitTagDelete",
    "NeogitCherryPick",
  },
  group = vim.api.nvim_create_augroup("GitStatusNeogit", { clear = true }),
  callback = function()
    _dir_to_toplevel[M.current_dir()] = nil
    M.trigger()
  end,
})

return M
