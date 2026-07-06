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
    if not require("util.buf").is_file(args.buf) then
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

-- Reopen a file at the last cursor position (the `"` mark). Skips commit
-- messages and similar always-start-fresh buffers. persistence.nvim only
-- covers files restored as part of a session; this covers every other open.
vim.api.nvim_create_autocmd("BufReadPost", {
  group = group,
  callback = function(args)
    if vim.tbl_contains({ "gitcommit", "gitrebase" }, vim.bo[args.buf].filetype) then
      return
    end
    local mark = vim.api.nvim_buf_get_mark(args.buf, '"')
    if mark[1] > 0 and mark[1] <= vim.api.nvim_buf_line_count(args.buf) then
      pcall(vim.api.nvim_win_set_cursor, 0, mark)
    end
  end,
})

-- Suppress LSP diagnostics, treesitter highlighting, AND markview rendering in
-- buffers with unresolved git conflict markers.
--
-- Diagnostics: language servers (lua_ls especially) parse `<<<<<<<` /
-- `=======` / `>>>>>>>` as code and spam syntax errors (`<<` reads as a
-- bit-shift op, `HEAD` as an undefined global).
--
-- Treesitter: the parser can't parse the markers either, so it mis-scopes
-- nodes — e.g. it smears markdown `@markup.heading.1` (and other) highlights
-- across marker/plain lines inconsistently. That's the "random red" in
-- diffview's merge buffer (verified via :Inspect: pure @markup.heading,no diff
-- extmark). Stopping the highlighter while markers are present makes the
-- conflicted buffer render as uniform plain text. The clean OURS/THEIRS panes
-- are separate marker-free buffers, so they keep their syntax highlighting.
--
-- Both are re-enabled ONLY on buffers we disabled, once markers resolve — so
-- this never fights the manual <leader>ud toggle.
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
    if not require("util.buf").is_file(buf) then
      return
    end
    if has_conflict_markers(buf) then
      vim.diagnostic.enable(false, { bufnr = buf })
      -- Scheduled: treesitter (FileType) AND markview both (re)attach AFTER this
      -- BufReadPost — a synchronous stop here would just be undone. Defer past
      -- that tick so it sticks. markview is the worst offender on a conflicted
      -- markdown buffer: its parser chokes on the markers and it renders garbage
      -- virtual-text (the per-char `P r e p` blocks were 7 markview virt extmarks)
      -- plus heading icons/colors over the conflict.
      -- Order matters: markview turns native treesitter highlighting OFF while
      -- it renders and turns it back ON when disabled — so disable markview
      -- FIRST, then stop treesitter, or markview's re-enable would undo the stop.
      vim.schedule(function()
        if vim.api.nvim_buf_is_valid(buf) then
          pcall(function()
            require("markview.commands").disable(buf)
          end)
          pcall(vim.treesitter.stop, buf)
        end
      end)
      conflict_disabled[buf] = true
    elseif conflict_disabled[buf] then
      vim.diagnostic.enable(true, { bufnr = buf })
      pcall(vim.treesitter.start, buf)
      pcall(function()
        require("markview.commands").enable(buf)
      end)
      conflict_disabled[buf] = nil
    end
  end,
})

-- Native merge-conflict keymaps: auto-attach util/merge.lua's buffer-local
-- <leader>c* bindings to any normal file buffer that contains git conflict
-- markers. Buffer-local so the keys only bind where there's a conflict. Works
-- in a plain file AND in the working/middle pane of a 3-way :diffsplit
-- (it edits the markers directly, so diff mode doesn't matter).
vim.api.nvim_create_autocmd({ "BufReadPost", "BufWinEnter" }, {
  group = vim.api.nvim_create_augroup("native-merge-keys", { clear = true }),
  callback = function(ev)
    if vim.b[ev.buf].merge_keys or not require("util.buf").is_file(ev.buf) then
      return
    end
    -- Don't collide with codediff: inside its merge view, codediff's own
    -- conflict keys (plugins/codediff.lua, same <leader>c* scheme) own the
    -- session buffers. util/merge is the path for conflicted files opened
    -- OUTSIDE a merge view (plain edit, neogit RET). codediff tracks sessions
    -- per-tabpage, so "this tab has a session" is the ownership test.
    local ok, lifecycle = pcall(require, "codediff.ui.lifecycle")
    if ok and lifecycle.get_session and lifecycle.get_session(vim.api.nvim_get_current_tabpage()) then
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

-- Close certain helper/utility buffers with `q`.
vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = {
    "checkhealth",
    "git",
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
