-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- Map jk and kj to escape in insert mode
vim.keymap.set("i", "jk", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "kj", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "jj", "<Esc>", { desc = "Exit insert mode" })
vim.keymap.set("i", "kk", "<Esc>", { desc = "Exit insert mode" })

-- Source current file
vim.keymap.set("n", "<leader>so", ":source %<CR>", { desc = "Source current file" })

-- Keep cursor centered when scrolling
vim.keymap.set("n", "<C-d>", "<C-d>zz", { desc = "Scroll down and center" })
vim.keymap.set("n", "<C-u>", "<C-u>zz", { desc = "Scroll up and center" })

-- Keep cursor centered when searching
vim.keymap.set("n", "n", "nzzzv", { desc = "Next search result and center" })
vim.keymap.set("n", "N", "Nzzzv", { desc = "Previous search result and center" })

-- Keep cursor centered when jumping between diff hunks (diffview / :diffsplit)
vim.keymap.set("n", "]c", "]czz", { desc = "Next hunk and center" })
vim.keymap.set("n", "[c", "[czz", { desc = "Previous hunk and center" })

-- Copy file paths
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

-- LSP restart + clear stale diagnostics
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

-- Fugitive (overrides LazyVim's lazygit defaults)
vim.keymap.set("n", "<leader>gg", "<cmd>tab Git<cr>", { desc = "Fugitive Status (tab)" })
-- Commit in a terminal split so pre-commit hook output (husky/eslint) is fully visible.
-- Fugitive's cc swallows failing-hook output (E21 / trimmed to one line) — terminal shows it all.
-- On exit, refresh fugitive's status buffer (the external commit happens outside fugitive's knowledge).
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
vim.keymap.set("n", "<leader>gP", "<cmd>Git push<cr>", { desc = "Git push" })
vim.keymap.set("n", "<leader>gp", "<cmd>Git pull<cr>", { desc = "Git pull" })
vim.keymap.set("n", "<leader>gl", "<cmd>Git log --oneline --decorate --all --graph<cr>", { desc = "Git log" })
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
    vim.notify("No :G status window open - run <leader>gg first", vim.log.levels.WARN)
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

-- Notification history (yankable buffer)
vim.keymap.set("n", "<leader>N", function() Snacks.notifier.show_history() end, { desc = "Notification history (yankable)" })

-- Toggle inlay hints
vim.keymap.set("n", "<leader>ih", function()
  local enabled = not vim.lsp.inlay_hint.is_enabled()
  vim.lsp.inlay_hint.enable(enabled)
  vim.g.lazyvim_inlay_hints = enabled
end, { desc = "Toggle inlay hints" })

-- Project-wide diagnostics
vim.keymap.set("n", "<leader>xp", function()
  local cwd = vim.fn.getcwd()
  local cmds = {}
  -- Search cwd and immediate subdirs for project markers
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
