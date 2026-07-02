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

-- Code-review keys (]c/[c, =) — full workflow cheatsheet lives in the header
-- of plugins/neogit.lua.
--
-- ]c/[c: native diff-mode change motion when the window is a real diff
-- (:diffsplit / nvim diff mode); otherwise gitsigns hunk navigation. Both center.
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
      -- No inline preview on jump — diff visibility is owned by `=`
      -- (whole-file inline overlay) / <leader>gd (diffthis). ]c/[c just navigate.
      pcall(gs.nav_hunk, direction, { preview = false, target = "all" }, function()
        vim.cmd("normal! zz")
      end)
    end
  end
end
vim.keymap.set("n", "]c", hunk_jump("next", "]czz"), { desc = "Next hunk and center" })
vim.keymap.set("n", "[c", hunk_jump("prev", "[czz"), { desc = "Previous hunk and center" })
-- ]h/[h: aliases for hunk nav (native diff motion is ]c/[c, so reuse it as the fallback).
vim.keymap.set("n", "]h", hunk_jump("next", "]czz"), { desc = "Next hunk and center" })
vim.keymap.set("n", "[h", hunk_jump("prev", "[czz"), { desc = "Previous hunk and center" })

-- `=`: TOGGLE the PERSISTENT whole-file inline diff overlay, matching neogit's
-- <CR> "open the file WHOLE, read in context" review gear — the everyday
-- "show me what changed here" key. Fires anywhere in the buffer (it's a
-- file-wide view; no cursor-on-a-hunk requirement). Native `=` reindent is
-- intentionally given up — conform format_on_save makes manual reindent moot.
-- Three gitsigns flags flip together, all synced to toggle_deleted's returned
-- state (they are GLOBAL config flags, so the overlay spans buffers while on):
--   show_deleted → removed lines as virtual lines (the OLD side)
--   linehl       → full-line background on added/changed lines (the NEW side —
--                  without this you "only see deleted lines")
--   word_diff    → intra-line changed-word highlights on line-for-line changes
-- Guarded off inside a real diff (vim.wo.diff) so it doesn't fight <leader>gd's
-- diffthis split. NOTE: j/k skip the virtual deleted lines (a Neovim core limit
-- on virt_lines) — scroll the overlay with <C-d>/<C-e>, or use <leader>gd
-- (:Gitsigns diffthis) for a real, line-navigable diff split.
vim.keymap.set("n", "=", function()
  local ok, gs = pcall(require, "gitsigns")
  if not ok or vim.wo.diff then
    return
  end
  local on = gs.toggle_deleted()
  gs.toggle_linehl(on)
  gs.toggle_word_diff(on)
end, { desc = "Toggle whole-file inline diff overlay" })

-- ─── Editing ──────────────────────────────────────────────────────────────────

-- Insert-mode undo break-points
vim.keymap.set("i", ",", ",<c-g>u")
vim.keymap.set("i", ".", ".<c-g>u")
vim.keymap.set("i", ";", ";<c-g>u")

-- Save file (works in insert/visual/normal/select)
vim.keymap.set({ "i", "x", "n", "s" }, "<C-s>", "<cmd>w<cr><esc>", { desc = "Save file" })

-- ─── Files & paths ────────────────────────────────────────────────────────────
-- Copy text to the system clipboard (+ register) and report it. `display`
-- overrides what's echoed when it differs from the copied text (e.g. a
-- truncated commit hash).
local function yank(text, display)
  vim.fn.setreg("+", text)
  vim.notify("Copied: " .. (display or text))
end

-- Absolute path of the current buffer's file, or nil (with a warning) for an
-- unnamed buffer. Thin UX wrapper over util.buf.path — the warning is keymaps'
-- concern, the path resolution is the shared primitive.
local function current_file()
  local abs = require("util.buf").path()
  if not abs then
    vim.notify("Buffer has no file", vim.log.levels.WARN)
  end
  return abs
end

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
  local abs = current_file()
  if not abs then
    return
  end
  local path, in_repo = require("util.git").relpath(abs)
  if not in_repo then
    vim.notify("Not in a git repo; copied absolute path", vim.log.levels.WARN)
  end
  yank(path)
end, { desc = "Copy git-root-relative path" })

vim.keymap.set("n", "<leader>yF", function()
  local abs = current_file()
  if not abs then
    return
  end
  yank(abs)
end, { desc = "Copy absolute path" })

vim.keymap.set("n", "<leader>yl", function()
  local abs = current_file()
  if not abs then
    return
  end
  local line = vim.api.nvim_win_get_cursor(0)[1]
  local path, in_repo = require("util.git").relpath(abs)
  if not in_repo then
    vim.notify("Not in a git repo; copied absolute path", vim.log.levels.WARN)
  end
  yank(path .. ":" .. line)
end, { desc = "Copy file:line reference" })

vim.keymap.set("n", "<leader>yb", function()
  local branch = require("util.git").branch()
  if not branch then
    vim.notify("Not on a branch", vim.log.levels.WARN)
    return
  end
  yank(branch)
end, { desc = "Copy git branch name" })

vim.keymap.set("n", "<leader>yc", function()
  local hash = require("util.git").head()
  if not hash then
    vim.notify("Not in a git repo", vim.log.levels.WARN)
    return
  end
  yank(hash, hash:sub(1, 12) .. "…")
end, { desc = "Copy git commit hash (HEAD)" })

vim.keymap.set("n", "<leader>fn", "<cmd>enew<cr>", { desc = "New File" })

-- Save file — mirrors Doom Emacs `SPC f s` (C-s also saves, see Editing section).
vim.keymap.set("n", "<leader>fs", "<cmd>w<cr>", { desc = "Save file" })

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
  require("util.scratch").open({
    name = "Messages",
    lines = vim.split(msgs, "\n"),
    split = "botright new",
    modifiable = true,
  })
end, { desc = "Messages (scratch buffer)" })

-- ─── Windows ──────────────────────────────────────────────────────────────────
vim.keymap.set("n", "<leader>wd", "<C-w>c", { desc = "Delete window" })
-- SPC w w cycles to the other window (Doom), not delete; delete moved to SPC w d.
vim.keymap.set("n", "<leader>ww", "<C-w>w", { desc = "Other window" })
vim.keymap.set("n", "<leader>w-", "<C-w>s", { desc = "Split window below" })
vim.keymap.set("n", "<leader>w|", "<C-w>v", { desc = "Split window right" })
-- Doom-style split aliases (SPC w s / SPC w v) alongside the -/| scheme above.
vim.keymap.set("n", "<leader>ws", "<C-w>s", { desc = "Split window below" })
vim.keymap.set("n", "<leader>wv", "<C-w>v", { desc = "Split window right" })
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
vim.keymap.set("n", "<leader>Tt", "<cmd>tabnew<cr>", { desc = "New Tab" })
vim.keymap.set("n", "<leader>Td", "<cmd>tabclose<cr>", { desc = "Close Tab" })
vim.keymap.set("n", "<leader>T]", "<cmd>tabnext<cr>", { desc = "Next Tab" })
vim.keymap.set("n", "<leader>T[", "<cmd>tabprevious<cr>", { desc = "Prev Tab" })
vim.keymap.set("n", "<leader>Tf", "<cmd>tabfirst<cr>", { desc = "First Tab" })
vim.keymap.set("n", "<leader>Tl", "<cmd>tablast<cr>", { desc = "Last Tab" })

-- ─── UI toggles ───────────────────────────────────────────────────────────────
-- Toggle dark (vivendi) ↔ light (operandi) across tmux AND nvim. Shells out to
-- the shared `theme-mode` script (single source of truth: it writes
-- ~/.cache/theme-mode and re-sources tmux), then applies the new mode here
-- immediately rather than waiting on theme-sync's ~1s poll. The ColorScheme
-- autocmd in plugins/theme.lua re-applies markview heading colours after.
vim.keymap.set("n", "<leader>ut", function()
  vim.system({ vim.fn.expand("~/.local/bin/theme-mode"), "toggle" }, {}, vim.schedule_wrap(function()
    require("config.theme-sync").apply_from_file(true)
  end))
end, { desc = "Toggle theme dark/light (tmux + nvim)" })
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
-- Toggle LSP semantic tokens for this buffer. Off = no async "white→color flip"
-- (tree-sitter only); on = type-accurate recoloring once the server responds.
vim.keymap.set("n", "<leader>uh", function()
  local bufnr = vim.api.nvim_get_current_buf()
  local enabled = vim.b[bufnr].semantic_tokens_enabled
  if enabled == nil then
    enabled = true
  end
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = bufnr })) do
    if client:supports_method("textDocument/semanticTokens/full") then
      if enabled then
        vim.lsp.semantic_tokens.stop(bufnr, client.id)
      else
        vim.lsp.semantic_tokens.start(bufnr, client.id)
      end
    end
  end
  vim.b[bufnr].semantic_tokens_enabled = not enabled
  vim.notify("Semantic tokens: " .. (enabled and "off" or "on"))
end, { desc = "Toggle semantic tokens" })

-- ─── Quit ─────────────────────────────────────────────────────────────────────
vim.keymap.set("n", "<leader>qq", "<cmd>qa<cr>", { desc = "Quit all" })

-- ─── Misc ─────────────────────────────────────────────────────────────────────
-- Plugin manager (vim.pack). Lives on <leader>P so <leader>p is free for the
-- project namespace (Doom `SPC p`).
vim.keymap.set("n", "<leader>Pp", "<cmd>PackStatus<cr>", { desc = "Plugins: status" })
vim.keymap.set("n", "<leader>PP", "<cmd>PackUpdate<cr>", { desc = "Plugins: update" })
vim.keymap.set("n", "<leader>PC", "<cmd>PackClean<cr>", { desc = "Plugins: clean" })
vim.keymap.set("n", "<leader>K", "<cmd>norm! K<cr>", { desc = "Keywordprg" })
-- Select entire file in Visual Line mode
vim.keymap.set("n", "<leader>va", "ggVG", { desc = "Select entire file" })
