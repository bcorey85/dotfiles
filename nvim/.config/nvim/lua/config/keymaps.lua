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
    vim.notify("Not a lua/vim file (ft=" .. ft .. ")", vim.log.levels.WARN)
    return
  end
  vim.cmd("source %")
  vim.notify("Sourced " .. vim.fn.expand("%:t"))
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
    vim.notify("Buffer has no file", vim.log.levels.WARN)
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
    vim.notify("Not in a git repo; copied absolute path", vim.log.levels.WARN)
  end
  vim.fn.setreg("+", path)
  vim.notify("Copied: " .. path)
end, { desc = "Copy git-root-relative path" })

vim.keymap.set("n", "<leader>yF", function()
  local path = vim.fn.expand("%:p")
  vim.fn.setreg("+", path)
  vim.notify("Copied: " .. path)
end, { desc = "Copy absolute path" })

vim.keymap.set("n", "<leader>yl", function()
  local abs = vim.fn.expand("%:p")
  if abs == "" then
    vim.notify("Buffer has no file", vim.log.levels.WARN)
    return
  end
  local line = vim.api.nvim_win_get_cursor(0)[1]
  local dir = vim.fn.fnamemodify(abs, ":h")
  local out = vim.fn.systemlist({ "git", "-C", dir, "rev-parse", "--show-toplevel" })
  local path = (vim.v.shell_error == 0 and out[1] and out[1] ~= "") and abs:sub(#out[1] + 2) or abs
  local ref = path .. ":" .. line
  vim.fn.setreg("+", ref)
  vim.notify("Copied: " .. ref)
end, { desc = "Copy file:line reference" })

vim.keymap.set("n", "<leader>yb", function()
  local branch = vim.fn.systemlist({ "git", "-C", vim.fn.getcwd(), "symbolic-ref", "--short", "HEAD" })[1]
  if vim.v.shell_error ~= 0 or not branch or branch == "" then
    vim.notify("Not on a branch", vim.log.levels.WARN)
    return
  end
  vim.fn.setreg("+", branch)
  vim.notify("Copied: " .. branch)
end, { desc = "Copy git branch name" })

vim.keymap.set("n", "<leader>yc", function()
  local hash = vim.fn.systemlist({ "git", "-C", vim.fn.getcwd(), "rev-parse", "HEAD" })[1]
  if vim.v.shell_error ~= 0 or not hash or hash == "" then
    vim.notify("Not in a git repo", vim.log.levels.WARN)
    return
  end
  vim.fn.setreg("+", hash)
  vim.notify("Copied: " .. hash:sub(1, 12) .. "…")
end, { desc = "Copy git commit hash (HEAD)" })

vim.keymap.set("n", "<leader>xr", function()
  vim.diagnostic.reset()
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = 0 })) do
    vim.lsp.stop_client(client.id, true)
  end
  vim.defer_fn(function()
    vim.api.nvim_exec_autocmds("FileType", { buffer = 0 })
    vim.notify("LSP restarted")
  end, 300)
end, { desc = "Restart LSP (clear diagnostics)" })

vim.keymap.set("n", "<leader>gc", "<cmd>Git commit<cr>", { desc = "Git commit" })
vim.keymap.set("n", "<leader>gp", "<cmd>Git pull<cr>", { desc = "Git pull" })
vim.keymap.set("n", "<leader>gF", "<cmd>Git push --force-with-lease<cr>", { desc = "Git push --force-with-lease" })
vim.keymap.set("n", "<leader>gP", "<cmd>Git push<cr>", { desc = "Git push" })
vim.keymap.set("n", "<leader>gf", "<cmd>Git fetch<cr>", { desc = "Git fetch" })
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
vim.keymap.set("n", "<leader>gl", function() require("neogit").open({ "log" }) end, { desc = "Git log (neogit)" })
vim.keymap.set("n", "<leader>gu", function() vim.cmd("DiffviewFileHistory --range=@{upstream}..HEAD") end, { desc = "Git log unpushed (diffview)" })
vim.keymap.set("n", "<leader>gb", function() require("mini.git").show_at_cursor() end, { desc = "Git blame line (float)" })
vim.keymap.set("n", "<leader>gB", "<cmd>Git blame -- %<cr>", { desc = "Git blame (file)" })

vim.keymap.set("n", "<leader>M", function()
  local msgs = vim.api.nvim_exec2("messages", { output = true }).output
  if msgs == "" then
    vim.notify("No messages")
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

vim.keymap.set("n", "<leader>N", function() require("mini.notify").show_history() end, { desc = "Notification history (yankable)" })

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
    vim.notify("No supported project found", vim.log.levels.WARN)
    return
  end
  local cmd = table.concat(cmds, "; ")
  vim.notify("Running project diagnostics...")
  vim.fn.jobstart(cmd, {
    cwd = cwd,
    stdout_buffered = true,
    on_stdout = function(_, data)
      vim.schedule(function()
        local lines = table.concat(data, "\n")
        if lines == "" then
          vim.notify("No errors found!")
          return
        end
        vim.fn.setqflist({}, " ", { title = "Project Diagnostics", lines = data })
        vim.cmd("copen")
      end)
    end,
  })
end, { desc = "Project-wide diagnostics" })

local function delete_other_buffers()
  local cur = vim.api.nvim_get_current_buf()
  for _, b in ipairs(vim.api.nvim_list_bufs()) do
    if b ~= cur and vim.bo[b].buflisted then
      require("mini.bufremove").delete(b)
    end
  end
end

vim.keymap.set("n", "<leader>bd", function() require("mini.bufremove").delete() end, { desc = "Delete buffer" })
vim.keymap.set("n", "<leader>bD", function() require("mini.bufremove").delete(0, true) end, { desc = "Delete buffer (force)" })
vim.keymap.set("n", "[b", "<cmd>bprevious<cr>", { desc = "Prev buffer" })
vim.keymap.set("n", "]b", "<cmd>bnext<cr>", { desc = "Next buffer" })

vim.keymap.set("n", "]q", "<cmd>cnext<cr>", { desc = "Next quickfix" })
vim.keymap.set("n", "[q", "<cmd>cprev<cr>", { desc = "Prev quickfix" })

vim.keymap.set("n", "<leader>xl", "<cmd>lopen<cr>", { desc = "Location list" })
vim.keymap.set("n", "<leader>xq", "<cmd>copen<cr>", { desc = "Quickfix list" })

vim.keymap.set("n", "<leader>wd", "<C-w>c", { desc = "Delete window" })
vim.keymap.set("n", "<leader>w-", "<C-w>s", { desc = "Split window below" })
vim.keymap.set("n", "<leader>w|", "<C-w>v", { desc = "Split window right" })
vim.keymap.set("n", "<leader>wm", function()
  if vim.t.zoomed then
    vim.cmd(vim.t.zoom_restore or "")
    vim.t.zoomed = false
  else
    vim.t.zoom_restore = vim.fn.winrestcmd()
    vim.cmd("resize | vertical resize")
    vim.t.zoomed = true
  end
end, { desc = "Toggle zoom" })

vim.keymap.set("n", "<leader>qq", "<cmd>qa<cr>", { desc = "Quit all" })

-- Buffer cycle
vim.keymap.set("n", "<S-h>", "<cmd>BufferLineCyclePrev<cr>", { desc = "Prev buffer" })
vim.keymap.set("n", "<S-l>", "<cmd>BufferLineCycleNext<cr>", { desc = "Next buffer" })
vim.keymap.set("n", "<leader>bo", function() delete_other_buffers() end, { desc = "Delete other buffers" })

-- Yank diagnostics on the current line to the clipboard
vim.keymap.set("n", "<leader>yd", function()
  local lnum = vim.api.nvim_win_get_cursor(0)[1] - 1
  local diags = vim.diagnostic.get(0, { lnum = lnum })
  if vim.tbl_isempty(diags) then
    vim.notify("No diagnostics on this line")
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
