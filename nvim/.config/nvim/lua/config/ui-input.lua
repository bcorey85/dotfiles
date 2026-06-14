-- Minimal vim.ui.input override: centered floating input box.
--
-- Replaces the bottom-corner cmdline prompt with a rounded floating window,
-- matching the border style used elsewhere in this config. No plugins — just
-- nvim API. vim.ui.select is routed through snacks.picker (picker.ui_select,
-- set in plugins/snacks.lua), so snacks owns all select pickers.
--
-- Esc behavior (differs from typical prompt UIs):
--   INSERT mode <Esc> → drop to normal mode so vim motions/operators work on the text.
--   NORMAL mode <Esc> or q → cancel (discard and close).
--   <CR> in either mode → confirm.
--
-- Geometry mirrors tiny-cmdline.nvim (lua/plugins/tiny-cmdline.lua):
--   width  = clamp(40, 140, floor(columns * 0.80)), further clamped to columns-4
--   row    = floor((lines - 1) / 2)       -- content_height=1, position.y="50%"
--   col    = floor((columns - width - 2) / 2)  -- border=1 each side, position.x="50%"
-- Keep this math in sync with tiny-cmdline's geometry() function when either changes.
--
-- Omission: opts.completion is not wired up. The native completion sources
-- that would need hooking (wildmenu, omnifunc) don't map cleanly into a
-- scratch buffer, and none of the callers in this config require it.

vim.ui.input = function(opts, on_confirm)
  opts = opts or {}

  local default = opts.default or ""
  local prompt = (opts.prompt or "Input"):gsub("[:%s]+$", "")

  -- Geometry: mirrors tiny-cmdline (position.x="50%", position.y="50%", border=1 each side).
  -- Width: 80% of columns, clamped [40, 140], then clamped to columns-4.
  -- Content-width floor: if the default text plus a small margin exceeds the
  -- computed width, expand up to the same max (140 / columns-4).
  local cols = vim.o.columns
  local lines = vim.o.lines
  local width_base = math.max(40, math.min(140, math.floor(cols * 0.80)))
  width_base = math.min(width_base, cols - 4)
  local width = math.max(width_base, math.min(#default + 10, math.min(140, cols - 4)))
  -- row/col: position.y="50%" → floor((lines - content_height) * 0.50), content_height=1
  --          position.x="50%" → floor((cols - width - b*2) * 0.50), b=1
  local row = math.floor((lines - 1) / 2)
  local col = math.floor((cols - width - 2) / 2)

  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, { default })

  -- No explicit border here: inherits vim.o.winborder set in config/options.lua
  -- (rounded on 0.11+; degrades to no border on 0.10, which is cosmetic-only).
  local win = vim.api.nvim_open_win(buf, true, {
    relative = "editor",
    style = "minimal",
    title = " " .. prompt .. " ",
    title_pos = "center",
    width = width,
    height = 1,
    row = row,
    col = col,
  })

  local done = false

  local function confirm()
    if done then
      return
    end
    done = true
    local text = vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1] or ""
    vim.cmd.stopinsert()
    if vim.api.nvim_win_is_valid(win) then
      vim.api.nvim_win_close(win, true)
    end
    on_confirm(text)
  end

  local function cancel()
    if done then
      return
    end
    done = true
    vim.cmd.stopinsert()
    if vim.api.nvim_win_is_valid(win) then
      vim.api.nvim_win_close(win, true)
    end
    on_confirm(nil)
  end

  local map_opts = { buffer = buf, nowait = true }
  vim.keymap.set("i", "<CR>", confirm, map_opts)
  vim.keymap.set("n", "<CR>", confirm, map_opts)
  -- INSERT <Esc>: drop to normal mode so vim motions work on the text.
  vim.keymap.set("i", "<Esc>", "<Esc>", map_opts)
  -- NORMAL <Esc> / q: cancel.
  vim.keymap.set("n", "<Esc>", cancel, map_opts)
  vim.keymap.set("n", "q", cancel, map_opts)

  -- Any other close path (e.g. :q, wincmd, autocmd) should cancel cleanly.
  vim.api.nvim_create_autocmd({ "WinClosed", "BufWipeout" }, {
    buffer = buf,
    once = true,
    callback = cancel,
  })

  -- startinsert! (equiv. to "A") positions the cursor after the last character,
  -- handling empty and non-empty defaults correctly.
  vim.cmd("startinsert!")
end
