-- Persistent inline hunk preview helpers, shared by the `=` peek key
-- (keymaps.lua) and <leader>gd (plugins/gitsigns.lua). Named hunk_preview rather
-- than gitsigns to avoid a basename clash with the gitsigns plugin module.
--
-- gitsigns' preview_hunk_inline() renders the hunk under the cursor as virtual
-- lines, but immediately registers a once=true CursorMoved/InsertEnter/BufLeave
-- autocmd (desc below) that wipes it on the next motion — so the diff vanishes
-- the instant you move, and j / <C-d> dismiss it before they can scroll a tall
-- diff. show_inline() strips that autocmd so the virt_lines persist and scroll.
-- The preview renders into the named extmark namespace below, which inline_shown
-- / clear_inline read so a toggle works no matter which key raised it.
local M = {}

-- gitsigns internals these helpers hook into (stable across v2.x). The
-- namespace is created the first time the preview module loads, so resolve it
-- lazily rather than caching at require time.
local PREVIEW_NS = "gitsigns_preview_inline"
local CLEAR_DESC = "Clear gitsigns inline preview"

local function preview_ns()
  return vim.api.nvim_get_namespaces()[PREVIEW_NS]
end

-- True if an inline preview is currently rendered in `buf` (default current).
function M.inline_shown(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  local ns = preview_ns()
  return ns ~= nil and #vim.api.nvim_buf_get_extmarks(buf, ns, 0, -1, {}) > 0
end

-- Clear any inline preview in `buf` (default current).
function M.clear_inline(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  local ns = preview_ns()
  if ns then
    vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  end
end

-- Render the persistent inline preview for the hunk under the cursor, then strip
-- gitsigns' auto-clear autocmd so it stays put and scrolls. No-ops (via
-- gitsigns) when the cursor isn't on a hunk. Schedule runs after
-- preview_hunk_inline has registered the autocmd.
function M.show_inline()
  local buf = vim.api.nvim_get_current_buf()
  require("gitsigns").preview_hunk_inline()
  vim.schedule(function()
    for _, au in ipairs(vim.api.nvim_get_autocmds({
      buffer = buf,
      event = { "CursorMoved", "InsertEnter", "BufLeave" },
    })) do
      if au.desc == CLEAR_DESC then
        pcall(vim.api.nvim_del_autocmd, au.id)
      end
    end
  end)
end

-- True if `row` (default cursor) falls within any hunk in `buf` (default
-- current) — unstaged (gitsigns' public get_hunks) OR staged (read straight from
-- the gitsigns cache's hunks_staged, the same internal set the -/_ stage maps
-- use; get_hunks reports unstaged only). The `=` peek key gates on this to
-- decide preview vs. native reindent; preview_hunk_inline itself handles
-- staged-vs-unstaged rendering, so this only answers "is the cursor on a hunk?".
function M.on_hunk(row, buf)
  buf = buf or vim.api.nvim_get_current_buf()
  row = row or vim.fn.line(".")
  local function in_any(hunks)
    for _, h in ipairs(hunks or {}) do
      local s = h.added.start
      local e = s + math.max(h.added.count, 1) - 1
      if row >= s and row <= e then
        return true
      end
    end
    return false
  end
  if in_any(require("gitsigns").get_hunks(buf)) then
    return true
  end
  local ok, cache = pcall(require, "gitsigns.cache")
  local bcache = ok and cache.cache[buf]
  return bcache ~= nil and in_any(bcache.hunks_staged)
end

-- Toggle the persistent inline preview: clear it if shown, else render it.
function M.toggle_inline()
  if M.inline_shown() then
    M.clear_inline()
  else
    M.show_inline()
  end
end

return M
