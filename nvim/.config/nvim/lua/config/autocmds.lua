local group = vim.api.nvim_create_augroup("user_autocmds", { clear = true })

vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" }, {
  group = group,
  callback = function()
    if vim.fn.getcmdwintype() == "" then
      vim.cmd("checktime")
    end
  end,
})

vim.api.nvim_create_autocmd("BufEnter", {
  group = group,
  callback = function(args)
    -- BufEnter fires on every window/buffer switch and picker preview. The git
    -- root is stable per buffer, so memoize to skip the vim.fs.root walk after
    -- the first enter. The lcd still re-applies each visit (cheap, and keeps the
    -- window-local cwd correct when revisiting a buffer from a different root).
    if vim.bo[args.buf].buftype ~= "" then
      return
    end
    local root = vim.b[args.buf].lcd_root
    if root == nil then
      local path = vim.api.nvim_buf_get_name(args.buf)
      if path == "" then
        return
      end
      root = vim.fs.root(path, { ".git" }) or false
      vim.b[args.buf].lcd_root = root
    end
    if root and root ~= vim.fn.getcwd(-1, 0) then
      pcall(vim.cmd.lcd, root)
    end
  end,
})

vim.api.nvim_create_autocmd({ "FocusGained", "TermClose", "TermLeave" }, {
  group = group,
  callback = function()
    if vim.o.buftype ~= "nofile" then
      vim.cmd("checktime")
    end
  end,
})

vim.api.nvim_create_autocmd({ "BufWritePre" }, {
  group = group,
  callback = function(event)
    if event.match:match("^%w%w+:[\\/][\\/]") then
      return
    end
    local file = vim.uv.fs_realpath(event.match) or event.match
    vim.fn.mkdir(vim.fn.fnamemodify(file, ":p:h"), "p")
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = { "markdown", "text", "gitcommit" },
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.linebreak = true
    vim.opt_local.spell = true
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = { "json", "jsonc", "json5" },
  callback = function()
    vim.opt_local.conceallevel = 0
  end,
})

vim.api.nvim_create_autocmd("TextYankPost", {
  group = group,
  callback = function()
    vim.hl.on_yank()
  end,
})

-- Suppress LSP diagnostics in buffers with unresolved git conflict markers.
-- Language servers (lua_ls especially) parse `<<<<<<<` / `=======` / `>>>>>>>`
-- as code and spam syntax errors (`<<` reads as a bit-shift op, `HEAD` as an
-- undefined global). Disable diagnostics while markers are present, and
-- re-enable ONLY the buffers we disabled once they resolve — so this never
-- fights the manual <leader>ud toggle.
local conflict_disabled = {}

-- vim.fn.search with "nw" is O(lines-until-match) and runs in the context of the
-- buffer, so it short-circuits on the first hit. This is faster than a Lua
-- full-buffer scan and stays consistent with the native-merge-keys check below.
local function has_conflict_markers(buf)
  return vim.api.nvim_buf_call(buf, function()
    return vim.fn.search([[^<<<<<<<]], "nw") ~= 0
  end)
end

vim.api.nvim_create_autocmd({ "BufReadPost", "BufWritePost" }, {
  group = vim.api.nvim_create_augroup("ConflictDiagnostics", { clear = true }),
  callback = function(args)
    local buf = args.buf
    if vim.bo[buf].buftype ~= "" then
      return
    end
    if has_conflict_markers(buf) then
      vim.diagnostic.enable(false, { bufnr = buf })
      conflict_disabled[buf] = true
    elseif conflict_disabled[buf] then
      vim.diagnostic.enable(true, { bufnr = buf })
      conflict_disabled[buf] = nil
    end
  end,
})

-- Native merge-conflict keymaps: auto-attach util/merge.lua's buffer-local
-- <leader>c* bindings to any normal file buffer that contains git conflict
-- markers. Buffer-local so the keys only bind where there's a conflict. Works
-- in a plain file AND in the working/middle pane of fugitive's 3-way diffsplit
-- (it edits the markers directly, so diff mode doesn't matter).
vim.api.nvim_create_autocmd({ "BufReadPost", "BufWinEnter" }, {
  group = vim.api.nvim_create_augroup("native-merge-keys", { clear = true }),
  callback = function(ev)
    if vim.b[ev.buf].merge_keys or vim.bo[ev.buf].buftype ~= "" then
      return
    end
    if has_conflict_markers(ev.buf) then
      require("util.merge").attach(ev.buf)
    end
  end,
})

vim.api.nvim_create_autocmd("VimResized", {
  group = group,
  callback = function()
    local current_tab = vim.fn.tabpagenr()
    vim.cmd("tabdo wincmd =")
    vim.cmd("tabnext " .. current_tab)
  end,
})

-- Close certain helper/utility buffers with `q`. grug-far is included so
-- <leader>sr can be dismissed with q.
vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = {
    "checkhealth",
    "git",
    "grug-far",
    "help",
    "lspinfo",
    "qf",
  },
  callback = function(event)
    vim.bo[event.buf].buflisted = false
    vim.schedule(function()
      vim.keymap.set("n", "q", function()
        vim.cmd("close")
        pcall(vim.api.nvim_buf_delete, event.buf, { force = true })
      end, {
        buffer = event.buf,
        silent = true,
        desc = "Quit buffer",
      })
    end)
  end,
})
