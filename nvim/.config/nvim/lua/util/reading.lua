-- Reading mode: zen + non-modifiable buffer + q to exit.
-- <leader>z stays plain editable zen (writing mode).
-- This module is invoked by a herdr keybinding that zooms the nvim pane first,
-- then calls toggle(). Pressing the binding again: herdr unzooms, toggle() closes
-- zen → on_close fires → cleanup(). cleanup() never touches herdr zoom because
-- the keybinding exit already handles unzoom — calling zoom toggle here would
-- double-toggle.

local M = {}

---@class ReadingState
---@field bufnr integer
---@field readonly boolean
---@field modifiable boolean

---@type ReadingState|nil
local state = nil

-- Restore buffer options and q map saved at open time. Idempotent: no-ops when
-- not active. Called from zen's on_close so every exit path (q, <leader>z,
-- :q in the zen win, or the herdr keybinding second press) restores the buffer
-- consistently.
function M.cleanup()
  if state == nil then
    return
  end

  local saved = state
  -- Clear state before any side-effectful work so a re-entrant call is a no-op.
  state = nil

  if vim.api.nvim_buf_is_valid(saved.bufnr) then
    -- Restore the ORIGINAL values, not blind false/true. A buffer opened via
    -- :view is readonly=true/modifiable=false by design; we must not change that.
    vim.bo[saved.bufnr].readonly = saved.readonly
    vim.bo[saved.bufnr].modifiable = saved.modifiable

    -- Buffer-local q map was set by toggle(); remove it. pcall guards the case
    -- where the user deleted it manually or the buffer type changed.
    pcall(vim.keymap.del, "n", "q", { buffer = saved.bufnr })
  end
end

-- Toggle reading mode. Opens zen + locks the buffer when inactive; closes zen
-- (triggering on_close → cleanup) when active. q is set buffer-local so it
-- never clobbers the global <nop> in keymaps.lua.
function M.toggle()
  -- Active: close zen. on_close fires → cleanup() does the rest.
  if state ~= nil then
    Snacks.zen()
    return
  end

  -- Inactive: open zen, then lock the buffer.
  Snacks.zen()

  local bufnr = vim.api.nvim_get_current_buf()

  -- Save existing values so cleanup restores exactly what was here before.
  state = {
    bufnr = bufnr,
    readonly = vim.bo[bufnr].readonly,
    modifiable = vim.bo[bufnr].modifiable,
  }

  vim.bo[bufnr].readonly = true
  vim.bo[bufnr].modifiable = false

  vim.keymap.set("n", "q", function()
    -- When inside a herdr zoom, unzoom first so the layout is restored before zen
    -- collapses the window; otherwise herdr leaves the pane in a half-zoomed state.
    if vim.env.HERDR_PANE_ID ~= nil then
      local result = vim.system({ "herdr", "pane", "layout", "--current" }):wait()
      local ok, layout = pcall(vim.json.decode, result.stdout or "{}")
      if ok and layout and layout.result and layout.result.layout and layout.result.layout.zoomed then
        vim.system({ "herdr", "pane", "zoom", "--current", "--toggle" }):wait()
      end
    end
    Snacks.zen()
  end, { buffer = bufnr, silent = true, desc = "Exit reading mode" })
end

return M
