-- ─── Disabled keys ────────────────────────────────────────────────────────────
vim.keymap.set("n", "q", "<nop>", { desc = "Disabled (was: record macro)" })
vim.keymap.set("n", "Q", "q", { desc = "Record macro (Qq starts, Q stops; @q replays)" })

-- ─── Insert-mode escape ───────────────────────────────────────────────────────
vim.keymap.set("i", "kk", "<Esc>", { desc = "Exit insert mode" })

vim.keymap.set({ "i", "n", "s" }, "<esc>", "<esc><cmd>noh<cr>", { silent = true, desc = "Escape and clear hlsearch" })

-- Movement & scrolling
vim.keymap.set({ "n", "x" }, "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true, desc = "Down" })
vim.keymap.set({ "n", "x" }, "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true, desc = "Up" })

vim.keymap.set("n", "<C-d>", "10<C-d>zz", { desc = "Scroll down and center" })
vim.keymap.set("n", "<C-u>", "10<C-u>zz", { desc = "Scroll up and center" })

-- Alternate file: toggle between the two most recent buffers (test ↔ impl). Mirrors tmux prefix-; alt-window.
vim.keymap.set("n", "<leader>;", "<C-^>", { desc = "Alternate file" })

vim.keymap.set("n", "n", "nzzzv", { desc = "Next search result and center" })
vim.keymap.set("n", "N", "Nzzzv", { desc = "Previous search result and center" })

-- Code-review keys (]c/[c, =) — full workflow cheatsheet lives in the header of
-- plugins/fugitive.lua.
--
-- ]c/[c: native diff-mode change motion when the window is a real diff
-- (fugitive :Gdiffsplit / :diffsplit); otherwise gitsigns hunk navigation. Both center.
local function hunk_jump(direction, native)
  return function()
    if vim.wo.diff then
      vim.cmd("normal! " .. native)
      return
    end
    local ok, gs = pcall(require, "gitsigns")
    if ok then
      -- preview = false so gitsigns doesn't open its floating window; show the
      -- hunk inline instead via the callback once the (async) nav completes.
      -- target="all" keeps staged hunks navigable; nav_hunk defaults to
      -- "unstaged", so without it a hunk drops out of the ]c walk the moment you
      -- stage it (gitsigns tracks the staged set via signs_staged_enable).
      -- No inline preview on jump — diff visibility is owned by <leader>gV
      -- (persistent whole-file inline diff). ]c/[c just navigate and center.
      pcall(gs.nav_hunk, direction, { preview = false, target = "all" }, function()
        vim.cmd("normal! zz")
      end)
    end
  end
end
vim.keymap.set("n", "]c", hunk_jump("next", "]czz"), { desc = "Next hunk and center" })
vim.keymap.set("n", "[c", hunk_jump("prev", "[czz"), { desc = "Previous hunk and center" })

-- `=`: TOGGLE gitsigns' inline preview (same display as <leader>gd). If a
-- preview is already up — wherever it came from — clear it; else, on a hunk
-- (staged or unstaged — on_hunk checks both), show it persistently (stays across
-- motion, scrolls with j / <C-d>); off a hunk with nothing shown, fall through
-- to the native `=` reindent operator. The persistence/toggle/scroll/on-hunk
-- mechanics live in util.hunk_preview (shared with <leader>gd). conform
-- format_on_save makes manual `=` rare, so hijacking it on changes is cheap, and
-- the feedkeys passthrough preserves =ip / gg=G off a hunk. Non-expr (expr maps
-- hit textlock when preview sets extmarks).
vim.keymap.set("n", "=", function()
  local ok = pcall(require, "gitsigns")
  if ok and not vim.wo.diff then
    local gsui = require("util.hunk_preview")
    if gsui.inline_shown() then
      gsui.clear_inline() -- already showing → toggle off
      return
    end
    if gsui.on_hunk() then
      gsui.show_inline()
      return
    end
  end
  vim.api.nvim_feedkeys("=", "n", false) -- not on a hunk: native operator
end, { desc = "Toggle inline hunk preview on a change, else = operator" })

-- ─── Editing ──────────────────────────────────────────────────────────────────

-- Insert-mode undo break-points
vim.keymap.set("i", ",", ",<c-g>u")
vim.keymap.set("i", ".", ".<c-g>u")
vim.keymap.set("i", ";", ";<c-g>u")

-- Save file (works in insert/visual/normal/select)
vim.keymap.set({ "i", "x", "n", "s" }, "<C-s>", "<cmd>w<cr><esc>", { desc = "Save file" })

-- ─── Files & paths ────────────────────────────────────────────────────────────
vim.keymap.set("n", "<leader>so", function()
  local ft = vim.bo.filetype
  if ft ~= "lua" and ft ~= "vim" then
    vim.notify("Not a lua/vim file (ft=" .. ft .. ")", vim.log.levels.WARN)
    return
  end
  vim.cmd("source %")
  vim.notify("Sourced " .. vim.fn.expand("%:t"))
end, { desc = "Source current file" })

vim.keymap.set("n", "<leader>yf", function()
  local abs = vim.fn.expand("%:p")
  if abs == "" then
    vim.notify("Buffer has no file", vim.log.levels.WARN)
    return
  end
  local path, in_repo = require("util.git").relpath(abs)
  if not in_repo then
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
  local path = require("util.git").relpath(abs)
  local ref = path .. ":" .. line
  vim.fn.setreg("+", ref)
  vim.notify("Copied: " .. ref)
end, { desc = "Copy file:line reference" })

vim.keymap.set("n", "<leader>yb", function()
  local branch = require("util.git").branch()
  if not branch then
    vim.notify("Not on a branch", vim.log.levels.WARN)
    return
  end
  vim.fn.setreg("+", branch)
  vim.notify("Copied: " .. branch)
end, { desc = "Copy git branch name" })

vim.keymap.set("n", "<leader>yc", function()
  local hash = require("util.git").head()
  if not hash then
    vim.notify("Not in a git repo", vim.log.levels.WARN)
    return
  end
  vim.fn.setreg("+", hash)
  vim.notify("Copied: " .. hash:sub(1, 12) .. "…")
end, { desc = "Copy git commit hash (HEAD)" })

vim.keymap.set("n", "<leader>fn", "<cmd>enew<cr>", { desc = "New File" })

-- ─── LSP & diagnostics ────────────────────────────────────────────────────────
vim.keymap.set("n", "<leader>lR", function()
  vim.diagnostic.reset()
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = 0 })) do
    client:stop(true)
  end
  vim.defer_fn(function()
    vim.api.nvim_exec_autocmds("FileType", { buffer = 0 })
    vim.notify("LSP restarted")
  end, 300)
end, { desc = "Restart LSP (clear diagnostics)" })

-- Apply every fixable LSP diagnostic in the current buffer in one shot.
-- `source.fixAll` is a standardized LSP code-action kind that eslint, ruff,
-- oxlint, biome, and most modern linters implement. Equivalent to running
-- :EslintFixAll for eslint, ruff's "Fix all" action, etc — but works
-- uniformly across whichever LSP is attached.
vim.keymap.set("n", "<leader>lA", function()
  vim.lsp.buf.code_action({
    apply = true,
    context = { only = { "source.fixAll" }, diagnostics = {} },
  })
end, { desc = "LSP: fix all (source.fixAll)" })

vim.keymap.set("n", "<leader>ui", function()
  local enabled = not vim.lsp.inlay_hint.is_enabled()
  vim.lsp.inlay_hint.enable(enabled)
end, { desc = "Toggle inlay hints" })

vim.keymap.set("n", "<leader>lp", require("util.diagnostics").project, { desc = "Project-wide diagnostics" })

vim.keymap.set("n", "<leader>yd", function()
  local lnum = vim.api.nvim_win_get_cursor(0)[1] - 1
  local diags = vim.diagnostic.get(0, { lnum = lnum })
  if vim.tbl_isempty(diags) then
    vim.notify("No diagnostics on this line")
    return
  end
  local msgs = vim.tbl_map(function(d)
    return d.message
  end, diags)
  local text = table.concat(msgs, "\n")
  vim.fn.setreg("+", text)
  vim.notify(("Yanked %d diagnostic(s)"):format(#diags))
end, { desc = "Yank line diagnostics" })

-- ─── Messages ─────────────────────────────────────────────────────────────────
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

-- ─── Windows ──────────────────────────────────────────────────────────────────
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

-- ─── Tabs ─────────────────────────────────────────────────────────────────────
vim.keymap.set("n", "<leader><tab><tab>", "<cmd>tabnew<cr>", { desc = "New Tab" })
vim.keymap.set("n", "<leader><tab>d", "<cmd>tabclose<cr>", { desc = "Close Tab" })
vim.keymap.set("n", "<leader><tab>]", "<cmd>tabnext<cr>", { desc = "Next Tab" })
vim.keymap.set("n", "<leader><tab>[", "<cmd>tabprevious<cr>", { desc = "Prev Tab" })
vim.keymap.set("n", "<leader><tab>f", "<cmd>tabfirst<cr>", { desc = "First Tab" })
vim.keymap.set("n", "<leader><tab>l", "<cmd>tablast<cr>", { desc = "Last Tab" })

-- ─── UI toggles ───────────────────────────────────────────────────────────────
vim.keymap.set("n", "<leader>uw", function()
  vim.wo.wrap = not vim.wo.wrap
end, { desc = "Toggle wrap" })
vim.keymap.set("n", "<leader>us", function()
  vim.wo.spell = not vim.wo.spell
end, { desc = "Toggle spell" })
vim.keymap.set("n", "<leader>ul", function()
  vim.wo.relativenumber = not vim.wo.relativenumber
end, { desc = "Toggle rel numbers" })
vim.keymap.set("n", "<leader>ud", function()
  vim.diagnostic.enable(not vim.diagnostic.is_enabled())
end, { desc = "Toggle diagnostics" })

-- ─── Quit ─────────────────────────────────────────────────────────────────────
vim.keymap.set("n", "<leader>qq", "<cmd>qa<cr>", { desc = "Quit all" })

-- ─── Misc ─────────────────────────────────────────────────────────────────────
-- Plugin manager (vim.pack)
vim.keymap.set("n", "<leader>pp", "<cmd>PackStatus<cr>", { desc = "Plugins: status" })
vim.keymap.set("n", "<leader>pP", "<cmd>PackUpdate<cr>", { desc = "Plugins: update" })
vim.keymap.set("n", "<leader>pC", "<cmd>PackClean<cr>", { desc = "Plugins: clean" })
vim.keymap.set("n", "<leader>K", "<cmd>norm! K<cr>", { desc = "Keywordprg" })
-- Select entire file in Visual Line mode
vim.keymap.set("n", "<leader>va", "ggVG", { desc = "Select entire file" })
