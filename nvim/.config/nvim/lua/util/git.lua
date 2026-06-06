-- Synchronous git helpers for on-demand keymaps and plugin callbacks.
-- statusline.lua deliberately keeps its own async `vim.system` path for
-- non-blocking renders — do not route that through here.
local M = {}

-- Run `git -C <dir> <args...>` synchronously; return the first stdout line,
-- or nil on any failure / empty output.
local function git_line(dir, args)
  local cmd = { "git", "-C", dir or vim.fn.getcwd() }
  vim.list_extend(cmd, args)
  local out = vim.fn.systemlist(cmd)
  if vim.v.shell_error ~= 0 or not out[1] or out[1] == "" then
    return nil
  end
  return out[1]
end

-- Absolute path of the repo toplevel containing `dir` (cwd if nil), or nil.
function M.root(dir)
  return git_line(dir, { "rev-parse", "--show-toplevel" })
end

-- Current branch short name, or nil if detached / not a repo.
function M.branch(dir)
  return git_line(dir, { "symbolic-ref", "--short", "HEAD" })
end

-- Full HEAD commit hash, or nil.
function M.head(dir)
  return git_line(dir, { "rev-parse", "HEAD" })
end

-- Git-root-relative path for an absolute file path. Returns (path, in_repo):
-- when in a repo, the root-relative path and true; otherwise the unchanged
-- absolute path and false, so callers can warn if they want.
function M.relpath(abs)
  local root = M.root(vim.fn.fnamemodify(abs, ":h"))
  if root then
    return abs:sub(#root + 2), true
  end
  return abs, false
end

return M
