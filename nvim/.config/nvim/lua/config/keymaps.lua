vim.keymap.set("n", "q", "<nop>", { desc = "Disabled (was: record macro)" })
vim.keymap.set("n", "Q", "<nop>", { desc = "Disabled (was: replay last macro)" })

vim.keymap.set("i", "jk", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "kj", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "jj", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "kk", "<Esc>", { desc = "Exit insert mode" })

vim.keymap.set({ "i", "n", "s" }, "<esc>", "<esc><cmd>noh<cr>", { silent = true, desc = "Escape and clear hlsearch" })

vim.keymap.set({ "n", "x" }, "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true, desc = "Down" })
vim.keymap.set({ "n", "x" }, "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true, desc = "Up" })

vim.keymap.set("n", "<leader>so", function()
  local ft = vim.bo.filetype
  if ft ~= "lua" and ft ~= "vim" then
    Snacks.notify.warn("Not a lua/vim file (ft=" .. ft .. ")")
    return
  end
  vim.cmd("source %")
  Snacks.notify("Sourced " .. vim.fn.expand("%:t"))
end, { desc = "Source current file" })

-- Save file (works in insert/visual/normal/select)
vim.keymap.set({ "i", "x", "n", "s" }, "<C-s>", "<cmd>w<cr><esc>", { desc = "Save file" })

vim.keymap.set("n", "<C-d>", "<C-d>zz", { desc = "Scroll down and center" })
vim.keymap.set("n", "<C-u>", "<C-u>zz", { desc = "Scroll up and center" })

vim.keymap.set("n", "n", "nzzzv", { desc = "Next search result and center" })
vim.keymap.set("n", "N", "Nzzzv", { desc = "Previous search result and center" })

-- Keep cursor centered when jumping between diff hunks (diffview / :diffsplit)
vim.keymap.set("n", "]c", "]czz", { desc = "Next hunk and center" })
vim.keymap.set("n", "[c", "[czz", { desc = "Previous hunk and center" })

vim.keymap.set("n", "<leader>yf", function()
  local abs = vim.fn.expand("%:p")
  if abs == "" then
    Snacks.notify.warn("Buffer has no file")
    return
  end
  local dir = vim.fn.fnamemodify(abs, ":h")
  local out = vim.fn.systemlist({ "git", "-C", dir, "rev-parse", "--show-toplevel" })
  local path
  if vim.v.shell_error == 0 and out[1] and out[1] ~= "" then
    local root = out[1]
    path = abs:sub(#root + 2)
  else
    path = abs
    Snacks.notify.warn("Not in a git repo; copied absolute path")
  end
  vim.fn.setreg("+", path)
  Snacks.notify("Copied: " .. path)
end, { desc = "Copy git-root-relative path" })

vim.keymap.set("n", "<leader>yF", function()
  local path = vim.fn.expand("%:p")
  vim.fn.setreg("+", path)
  Snacks.notify("Copied: " .. path)
end, { desc = "Copy absolute path" })

vim.keymap.set("n", "<leader>yl", function()
  local abs = vim.fn.expand("%:p")
  if abs == "" then
    Snacks.notify.warn("Buffer has no file")
    return
  end
  local line = vim.api.nvim_win_get_cursor(0)[1]
  local dir = vim.fn.fnamemodify(abs, ":h")
  local out = vim.fn.systemlist({ "git", "-C", dir, "rev-parse", "--show-toplevel" })
  local path = (vim.v.shell_error == 0 and out[1] and out[1] ~= "") and abs:sub(#out[1] + 2) or abs
  local ref = path .. ":" .. line
  vim.fn.setreg("+", ref)
  Snacks.notify("Copied: " .. ref)
end, { desc = "Copy file:line reference" })

vim.keymap.set("n", "<leader>yb", function()
  local branch = vim.fn.systemlist({ "git", "-C", vim.fn.getcwd(), "symbolic-ref", "--short", "HEAD" })[1]
  if vim.v.shell_error ~= 0 or not branch or branch == "" then
    Snacks.notify.warn("Not on a branch")
    return
  end
  vim.fn.setreg("+", branch)
  Snacks.notify("Copied: " .. branch)
end, { desc = "Copy git branch name" })

vim.keymap.set("n", "<leader>yc", function()
  local hash = vim.fn.systemlist({ "git", "-C", vim.fn.getcwd(), "rev-parse", "HEAD" })[1]
  if vim.v.shell_error ~= 0 or not hash or hash == "" then
    Snacks.notify.warn("Not in a git repo")
    return
  end
  vim.fn.setreg("+", hash)
  Snacks.notify("Copied: " .. hash:sub(1, 12) .. "…")
end, { desc = "Copy git commit hash (HEAD)" })

vim.keymap.set("n", "<leader>xr", function()
  vim.diagnostic.reset()
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = 0 })) do
    vim.lsp.stop_client(client.id, true)
  end
  vim.defer_fn(function()
    vim.api.nvim_exec_autocmds("FileType", { buffer = 0 })
    Snacks.notify("LSP restarted")
  end, 300)
end, { desc = "Restart LSP (clear diagnostics)" })

vim.keymap.set("n", "<leader>gs", "<cmd>tab Git<cr>", { desc = "Fugitive Status (tab)" })

vim.keymap.set("n", "<leader>gc", function()
  vim.ui.input({ prompt = "Commit message: " }, function(msg)
    if not msg or msg == "" then
      return
    end
    vim.cmd("botright 15split | enew")
    vim.fn.jobstart({ "git", "commit", "-m", msg }, {
      term = true,
      on_exit = function()
        vim.schedule(function()
          pcall(vim.fn["fugitive#DidChange"])
        end)
      end,
    })
    vim.cmd("startinsert")
  end)
end, { desc = "Git commit (terminal — shows hook output)" })

vim.keymap.set("n", "<leader>gp", "<cmd>Git push<cr>", { desc = "Git push" })
vim.keymap.set("n", "<leader>gF", "<cmd>Git push --force-with-lease<cr>", { desc = "Git push --force-with-lease" })
vim.keymap.set("n", "<leader>gP", "<cmd>Git pull<cr>", { desc = "Git pull" })
vim.keymap.set("n", "<leader>gt", function()
  local branch = vim.fn.systemlist("git symbolic-ref --short HEAD")[1]
  if not branch or branch == "" then
    Snacks.notify.warn("Not on a branch")
    return
  end
  vim.ui.input({ prompt = "Remote tracking branch: ", default = branch }, function(input)
    if not input or input == "" then return end
    vim.cmd("Git push -u origin " .. input)
  end)
end, { desc = "Git push + set upstream tracking (prompt)" })
vim.keymap.set("n", "<leader>gl", "<cmd>Git log --oneline --decorate --all --graph<cr>", { desc = "Git log" })
vim.keymap.set("n", "<leader>gu", function()
  vim.cmd("Git log @{u}..HEAD --oneline --decorate")
  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = true, desc = "Close unpushed log" })
end, { desc = "Git log unpushed commits" })
vim.keymap.set("n", "<leader>gb", function() Snacks.git.blame_line() end, { desc = "Git blame line (float)" })

vim.keymap.set("n", "<leader>gB", function()
  local file = vim.fn.expand("%:p")
  if file == "" then
    Snacks.notify.warn("No file in buffer")
    return
  end
  local dir = vim.fn.fnamemodify(file, ":h")
  vim.fn.system({ "git", "-C", dir, "rev-parse", "--git-dir" })
  if vim.v.shell_error ~= 0 then
    Snacks.notify.warn("Not in a git repository")
    return
  end
  require("lazy").load({ plugins = { "vim-fugitive" } })
  vim.fn.FugitiveDetect(dir)
  vim.api.nvim_create_autocmd("FileType", {
    pattern = "fugitiveblame",
    once = true,
    callback = function(args)
      vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = args.buf, silent = true })
    end,
  })
  vim.cmd("Git blame")
end, { desc = "Git blame (file)" })
-- Tear down a Gvdiffsplit from ANY window. Fugitive's built-in `dq` is
-- buffer-local to its own buffers (the :G summary and the fugitive:// object
-- side), so it won't fire from the working-tree file you land on after
-- reviewing. This walks the tab's windows instead: closes the HEAD/index side
-- and clears diff mode. Returns the :G summary window if one is open.
local function close_fugitive_diff()
  local status_win
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local buf = vim.api.nvim_win_get_buf(win)
    if vim.bo[buf].filetype == "fugitive" then
      status_win = win
    elseif vim.api.nvim_buf_get_name(buf):match("^fugitive://") then
      pcall(vim.api.nvim_win_close, win, false)
    end
  end
  vim.cmd("diffoff!")
  return status_win
end

-- Close the current diff and return focus to the status list.
vim.keymap.set("n", "<leader>gq", function()
  local status_win = close_fugitive_diff()
  if status_win and vim.api.nvim_win_is_valid(status_win) then
    vim.api.nvim_set_current_win(status_win)
  end
end, { desc = "Close fugitive diff (from any pane) -> status" })

vim.keymap.set("n", "<leader>M", function()
  local msgs = vim.api.nvim_exec2("messages", { output = true }).output
  if msgs == "" then
    Snacks.notify("No messages")
    return
  end
  vim.cmd("botright new")
  vim.api.nvim_buf_set_lines(0, 0, -1, false, vim.split(msgs, "\n"))
  vim.bo.buftype = "nofile"
  vim.bo.bufhidden = "wipe"
  vim.bo.swapfile = false
  vim.api.nvim_buf_set_name(0, "Messages")
  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = true, silent = true })
end, { desc = "Messages (scratch buffer)" })

vim.keymap.set("n", "<leader>N", function() Snacks.notifier.show_history() end, { desc = "Notification history (yankable)" })

vim.keymap.set("n", "<leader>ih", function()
  local enabled = not vim.lsp.inlay_hint.is_enabled()
  vim.lsp.inlay_hint.enable(enabled)
end, { desc = "Toggle inlay hints" })

-- Apply every fixable LSP diagnostic in the current buffer in one shot.
-- `source.fixAll` is a standardized LSP code-action kind that eslint, ruff,
-- oxlint, biome, and most modern linters implement. Equivalent to running
-- :EslintFixAll for eslint, ruff's "Fix all" action, etc — but works
-- uniformly across whichever LSP is attached.
vim.keymap.set("n", "<leader>cA", function()
  vim.lsp.buf.code_action({
    apply = true,
    context = { only = { "source.fixAll" }, diagnostics = {} },
  })
end, { desc = "LSP: fix all (source.fixAll)" })

vim.keymap.set("n", "<leader>xp", function()
  local cwd = vim.fn.getcwd()
  local cmds = {}
  local dirs = { cwd }
  for _, entry in ipairs(vim.fn.readdir(cwd)) do
    local path = cwd .. "/" .. entry
    if vim.fn.isdirectory(path) == 1 and entry ~= "node_modules" and entry ~= ".venv" then
      table.insert(dirs, path)
    end
  end
  local seen = {}
  for _, dir in ipairs(dirs) do
    if not seen[dir] then
      seen[dir] = true
      if vim.fn.filereadable(dir .. "/tsconfig.json") == 1 then
        table.insert(cmds, "cd " .. vim.fn.shellescape(dir) .. " && npx vue-tsc --noEmit 2>&1 || npx tsc --noEmit 2>&1")
      end
      if vim.fn.filereadable(dir .. "/pyproject.toml") == 1 then
        table.insert(cmds, "cd " .. vim.fn.shellescape(dir) .. " && uv run pyright 2>&1")
      end
    end
  end
  if #cmds == 0 then
    Snacks.notify("No supported project found", { level = "warn" })
    return
  end
  local cmd = table.concat(cmds, "; ")
  Snacks.notify("Running project diagnostics...")
  vim.fn.jobstart(cmd, {
    cwd = cwd,
    stdout_buffered = true,
    on_stdout = function(_, data)
      vim.schedule(function()
        local lines = table.concat(data, "\n")
        if lines == "" then
          Snacks.notify("No errors found!")
          return
        end
        vim.fn.setqflist({}, " ", { title = "Project Diagnostics", lines = data })
        vim.cmd("copen")
      end)
    end,
  })
end, { desc = "Project-wide diagnostics" })

vim.keymap.set("n", "<leader>bd", function() Snacks.bufdelete() end, { desc = "Delete buffer" })
vim.keymap.set("n", "<leader>bD", function() Snacks.bufdelete({ force = true }) end, { desc = "Delete buffer (force)" })
vim.keymap.set("n", "[b", "<cmd>bprevious<cr>", { desc = "Prev buffer" })
vim.keymap.set("n", "]b", "<cmd>bnext<cr>", { desc = "Next buffer" })

vim.keymap.set("n", "]q", "<cmd>cnext<cr>", { desc = "Next quickfix" })
vim.keymap.set("n", "[q", "<cmd>cprev<cr>", { desc = "Prev quickfix" })

vim.keymap.set("n", "<leader>xl", "<cmd>lopen<cr>", { desc = "Location list" })
vim.keymap.set("n", "<leader>xq", "<cmd>copen<cr>", { desc = "Quickfix list" })

vim.keymap.set("n", "<leader>wd", "<C-w>c", { desc = "Delete window" })
vim.keymap.set("n", "<leader>w-", "<C-w>s", { desc = "Split window below" })
vim.keymap.set("n", "<leader>w|", "<C-w>v", { desc = "Split window right" })

vim.keymap.set("n", "<leader>qq", "<cmd>qa<cr>", { desc = "Quit all" })

-- Pickers (Snacks)
vim.keymap.set("n", "<leader><leader>", function() Snacks.picker.smart({ cwd = require("util.root").get() }) end, { desc = "Smart find" })
vim.keymap.set("n", "<leader>/", function() Snacks.picker.grep({ cwd = require("util.root").get() }) end, { desc = "Grep (Root Dir)" })
vim.keymap.set("n", "<leader>ff", function() Snacks.picker.files({ cwd = require("util.root").get() }) end, { desc = "Find files (Root Dir)" })
vim.keymap.set("n", "<leader>fF", function() Snacks.picker.files({ hidden = true, ignored = true }) end, { desc = "Find files (all)" })
vim.keymap.set("n", "<leader>fr", function() Snacks.picker.recent() end, { desc = "Recent files" })
vim.keymap.set("n", "<leader>fb", function() Snacks.picker.buffers() end, { desc = "Buffers" })
vim.keymap.set("n", "<leader>fc", function() Snacks.picker.files({ cwd = vim.fn.stdpath("config") }) end, { desc = "Config files" })

-- Search
vim.keymap.set("n", "<leader>sg", function() Snacks.picker.grep({ cwd = require("util.root").get() }) end, { desc = "Grep (Root Dir)" })
vim.keymap.set("n", "<leader>sG", function() Snacks.picker.grep({ cwd = vim.fn.getcwd() }) end, { desc = "Grep (cwd)" })
vim.keymap.set({ "n", "x" }, "<leader>sw", function() Snacks.picker.grep_word({ cwd = require("util.root").get() }) end, { desc = "Grep word/selection (Root Dir)" })
vim.keymap.set({ "n", "x" }, "<leader>sW", function() Snacks.picker.grep_word({ cwd = vim.fn.getcwd() }) end, { desc = "Grep word/selection (cwd)" })
vim.keymap.set("n", "<leader>sR", function() Snacks.picker.resume() end, { desc = "Resume picker" })
vim.keymap.set("n", "<leader>sd", function() Snacks.picker.diagnostics() end, { desc = "Diagnostics (picker)" })

-- Buffer cycle
vim.keymap.set("n", "<S-h>", "<cmd>BufferLineCyclePrev<cr>", { desc = "Prev buffer" })
vim.keymap.set("n", "<S-l>", "<cmd>BufferLineCycleNext<cr>", { desc = "Next buffer" })
vim.keymap.set("n", "<leader>bo", function() Snacks.bufdelete.other() end, { desc = "Delete other buffers" })

-- Diagnostics list shortcut
vim.keymap.set("n", "<leader>xx", function() Snacks.picker.diagnostics() end, { desc = "Diagnostics list" })

-- Yank diagnostics on the current line to the clipboard
vim.keymap.set("n", "<leader>yd", function()
  local lnum = vim.api.nvim_win_get_cursor(0)[1] - 1
  local diags = vim.diagnostic.get(0, { lnum = lnum })
  if vim.tbl_isempty(diags) then
    Snacks.notify("No diagnostics on this line")
    return
  end
  local msgs = vim.tbl_map(function(d) return d.message end, diags)
  local text = table.concat(msgs, "\n")
  vim.fn.setreg("+", text)
  Snacks.notify(("Yanked %d diagnostic(s)"):format(#diags))
end, { desc = "Yank line diagnostics" })

-- UI toggles
vim.keymap.set("n", "<leader>uw", function() vim.wo.wrap = not vim.wo.wrap end, { desc = "Toggle wrap" })
vim.keymap.set("n", "<leader>us", function() vim.wo.spell = not vim.wo.spell end, { desc = "Toggle spell" })
vim.keymap.set("n", "<leader>ul", function() vim.wo.relativenumber = not vim.wo.relativenumber end, { desc = "Toggle rel numbers" })
vim.keymap.set("n", "<leader>ud", function() vim.diagnostic.enable(not vim.diagnostic.is_enabled()) end, { desc = "Toggle diagnostics" })

-- Move lines
vim.keymap.set("n", "<A-j>", "<cmd>execute 'move .+' . v:count1<cr>==", { desc = "Move down" })
vim.keymap.set("n", "<A-k>", "<cmd>execute 'move .-' . (v:count1 + 1)<cr>==", { desc = "Move up" })
vim.keymap.set("i", "<A-j>", "<esc><cmd>m .+1<cr>==gi", { desc = "Move down" })
vim.keymap.set("i", "<A-k>", "<esc><cmd>m .-2<cr>==gi", { desc = "Move up" })
vim.keymap.set("v", "<A-j>", ":<C-u>execute \"'<,'>move '>+\" . v:count1<cr>gv=gv", { desc = "Move down" })
vim.keymap.set("v", "<A-k>", ":<C-u>execute \"'<,'>move '<-\" . (v:count1 + 1)<cr>gv=gv", { desc = "Move up" })

-- Insert-mode undo break-points
vim.keymap.set("i", ",", ",<c-g>u")
vim.keymap.set("i", ".", ".<c-g>u")
vim.keymap.set("i", ";", ";<c-g>u")

vim.keymap.set("n", "<leader>l", "<cmd>Lazy<cr>", { desc = "Lazy" })
vim.keymap.set("n", "<leader>fn", "<cmd>enew<cr>", { desc = "New File" })
vim.keymap.set("n", "<leader>K", "<cmd>norm! K<cr>", { desc = "Keywordprg" })

-- Tabs
vim.keymap.set("n", "<leader><tab><tab>", "<cmd>tabnew<cr>", { desc = "New Tab" })
vim.keymap.set("n", "<leader><tab>d", "<cmd>tabclose<cr>", { desc = "Close Tab" })
vim.keymap.set("n", "<leader><tab>]", "<cmd>tabnext<cr>", { desc = "Next Tab" })
vim.keymap.set("n", "<leader><tab>[", "<cmd>tabprevious<cr>", { desc = "Prev Tab" })
vim.keymap.set("n", "<leader><tab>f", "<cmd>tabfirst<cr>", { desc = "First Tab" })
vim.keymap.set("n", "<leader><tab>l", "<cmd>tablast<cr>", { desc = "Last Tab" })
