-- Minimal vim.ui.input override: centered floating input box.
--
-- Replaces the bottom-corner cmdline prompt with a rounded floating window,
-- matching the border style used elsewhere in this config. No plugins — just
-- nvim API. vim.ui.select is intentionally left alone; telescope owns pickers.
--
-- Omission: opts.completion is not wired up. The native completion sources
-- that would need hooking (wildmenu, omnifunc) don't map cleanly into a
-- scratch buffer, and none of the callers in this config require it.

vim.ui.input = function(opts, on_confirm)
  opts = opts or {}

  local default = opts.default or ""
  local prompt = (opts.prompt or "Input"):gsub("[:%s]+$", "")

  local col_max = vim.o.columns - 4
  local width = math.min(math.max(40, #default + 10), col_max)
  local row = math.floor((vim.o.lines - 3) / 2)
  local col = math.floor((vim.o.columns - width) / 2)

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
  vim.keymap.set("i", "<Esc>", cancel, map_opts)
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
