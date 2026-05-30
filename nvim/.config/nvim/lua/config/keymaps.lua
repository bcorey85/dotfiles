vim.keymap.set("i", "jk", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "kj", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "jj", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "kk", "<Esc>", { desc = "Exit insert mode" })

vim.keymap.set({ "i", "n", "s" }, "<esc>", "<esc><cmd>noh<cr>", { silent = true, desc = "Escape and clear hlsearch" })

vim.keymap.set({ "n", "x" }, "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true, desc = "Down" })
vim.keymap.set({ "n", "x" }, "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true, desc = "Up" })

vim.keymap.set("n", "<leader>so", ":source %<CR>", { desc = "Source current file" })

-- Save file (works in insert/visual/normal/select), LazyVim-style
vim.keymap.set({ "i", "x", "n", "s" }, "<C-s>", "<cmd>w<cr><esc>", { desc = "Save file" })

vim.keymap.set("n", "<C-d>", "<C-d>zz", { desc = "Scroll down and center" })
vim.keymap.set("n", "<C-u>", "<C-u>zz", { desc = "Scroll up and center" })

vim.keymap.set("n", "n", "nzzzv", { desc = "Next search result and center" })
vim.keymap.set("n", "N", "Nzzzv", { desc = "Previous search result and center" })

-- Keep cursor centered when jumping between diff hunks (diffview / :diffsplit)
vim.keymap.set("n", "]c", "]czz", { desc = "Next hunk and center" })
vim.keymap.set("n", "[c", "[czz", { desc = "Previous hunk and center" })

vim.keymap.set("n", "<leader>fy", function()
  local path = vim.fn.expand("%")
  vim.fn.setreg("+", path)
  Snacks.notify("Copied: " .. path)
end, { desc = "Copy relative path" })

vim.keymap.set("n", "<leader>fY", function()
  local path = vim.fn.expand("%:p")
  vim.fn.setreg("+", path)
  Snacks.notify("Copied: " .. path)
end, { desc = "Copy absolute path" })

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

vim.keymap.set("n", "<leader>gf", "<cmd>tab Git<cr>", { desc = "Fugitive Status (tab)" })

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
vim.keymap.set("n", "<leader>gP", "<cmd>Git pull<cr>", { desc = "Git pull" })
vim.keymap.set("n", "<leader>gt", function()
  local branch = vim.fn.systemlist("git symbolic-ref --short HEAD")[1]
  if not branch or branch == "" then
    vim.notify("Not on a branch", vim.log.levels.WARN)
    return
  end
  vim.ui.input({ prompt = "Remote tracking branch: ", default = branch }, function(input)
    if not input or input == "" then return end
    vim.cmd("Git push -u origin " .. input)
  end)
end, { desc = "Git push + set upstream tracking (prompt)" })
vim.keymap.set("n", "<leader>gl", "<cmd>Git log --oneline --decorate --all --graph<cr>", { desc = "Git log" })
vim.keymap.set("n", "<leader>gu", "<cmd>Git log @{u}..HEAD --oneline --decorate<cr>", { desc = "Git log unpushed commits" })
vim.keymap.set("n", "<leader>gB", "<cmd>Git blame<cr>", { desc = "Git blame (file)" })
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

-- Review loop: close the current diff, jump to the NEXT changed file, and open
-- its vertical diff - one key instead of repeating dv. `)` advances to the next
-- file and `dv` opens the split; "m" replays them through fugitive's
-- buffer-local maps.
vim.keymap.set("n", "<leader>gn", function()
  local status_win = close_fugitive_diff()
  if not (status_win and vim.api.nvim_win_is_valid(status_win)) then
    vim.notify("No :G status window open - run <leader>gf first", vim.log.levels.WARN)
    return
  end
  vim.api.nvim_set_current_win(status_win)
  vim.api.nvim_feedkeys(")dv", "m", false)
end, { desc = "Review next changed file (close + next + vdiff)" })

vim.keymap.set("n", "<leader>gm", function()
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

vim.keymap.set("n", "<leader>bd", "<cmd>bdelete<cr>", { desc = "Delete buffer" })
vim.keymap.set("n", "<leader>bD", "<cmd>bdelete!<cr>", { desc = "Delete buffer (force)" })
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
vim.keymap.set("n", "<leader><leader>", function() Snacks.picker.smart() end, { desc = "Smart find" })
vim.keymap.set("n", "<leader>/", function() Snacks.picker.grep() end, { desc = "Grep (cwd)" })
vim.keymap.set("n", "<leader>ff", function() Snacks.picker.files() end, { desc = "Find files" })
vim.keymap.set("n", "<leader>fF", function() Snacks.picker.files({ hidden = true, ignored = true }) end, { desc = "Find files (all)" })
vim.keymap.set("n", "<leader>fr", function() Snacks.picker.recent() end, { desc = "Recent files" })
vim.keymap.set("n", "<leader>fb", function() Snacks.picker.buffers() end, { desc = "Buffers" })
vim.keymap.set("n", "<leader>fc", function() Snacks.picker.files({ cwd = vim.fn.stdpath("config") }) end, { desc = "Config files" })

-- Search
vim.keymap.set("n", "<leader>sg", function() Snacks.picker.grep() end, { desc = "Grep" })
vim.keymap.set({ "n", "x" }, "<leader>sw", function() Snacks.picker.grep_word() end, { desc = "Grep word/selection" })
vim.keymap.set("n", "<leader>sR", function() Snacks.picker.resume() end, { desc = "Resume picker" })
vim.keymap.set("n", "<leader>sd", function() Snacks.picker.diagnostics() end, { desc = "Diagnostics (picker)" })

-- Buffer cycle
vim.keymap.set("n", "<S-h>", "<cmd>BufferLineCyclePrev<cr>", { desc = "Prev buffer" })
vim.keymap.set("n", "<S-l>", "<cmd>BufferLineCycleNext<cr>", { desc = "Next buffer" })
vim.keymap.set("n", "<leader>bo", function() Snacks.bufdelete.other() end, { desc = "Delete other buffers" })

-- Diagnostics list shortcut
vim.keymap.set("n", "<leader>xx", function() Snacks.picker.diagnostics() end, { desc = "Diagnostics list" })

-- Yank diagnostics on the current line to the clipboard
vim.keymap.set("n", "<leader>cy", function()
  local lnum = vim.api.nvim_win_get_cursor(0)[1] - 1
  local diags = vim.diagnostic.get(0, { lnum = lnum })
  if vim.tbl_isempty(diags) then
    vim.notify("No diagnostics on this line", vim.log.levels.INFO)
    return
  end
  local msgs = vim.tbl_map(function(d) return d.message end, diags)
  local text = table.concat(msgs, "\n")
  vim.fn.setreg("+", text)
  vim.notify(("Yanked %d diagnostic(s)"):format(#diags))
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
