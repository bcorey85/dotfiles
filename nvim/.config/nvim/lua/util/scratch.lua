-- Open a throwaway scratch buffer in a new split, populate it, and bind `q` to
-- close. Used for read-only readouts (the :messages dump, the Claude review
-- preview) — the "nofile buffer + buftype/bufhidden + q-to-close" pattern that
-- was hand-rolled in keymaps.lua and review.lua.
local M = {}

-- opts:
--   name        buffer name (shown in winbar/statusline)
--   lines       array of lines to fill (default {})
--   filetype    optional filetype, e.g. "markdown"
--   split       split command, default "new" (e.g. "botright new")
--   modifiable  leave the buffer editable when true; default false (locked)
function M.open(opts)
  vim.cmd(opts.split or "new")
  vim.bo.buftype = "nofile"
  vim.bo.bufhidden = "wipe"
  vim.bo.swapfile = false
  if opts.filetype then
    vim.bo.filetype = opts.filetype
  end
  vim.api.nvim_buf_set_name(0, opts.name)
  vim.api.nvim_buf_set_lines(0, 0, -1, false, opts.lines or {})
  vim.bo.modifiable = opts.modifiable == true
  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = true, silent = true })
end

return M
