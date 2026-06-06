require("config.clipboard")

vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

vim.opt.autowrite = true
vim.opt.clipboard = "unnamedplus"
-- vim._core.ui2 is the 0.12 stable name for the experimental native message UI
-- (was vim._extui in pre-release builds; private path, may move again in future).
-- When available, route messages to a floating ephemeral window and reclaim the
-- cmdline row with cmdheight=0. Falls back to cmdheight=1 on older nvim (WSL/
-- Ubuntu/Arch machines that ship 0.10/0.11) so classic cmdline still works there.
local _ui2_ok, _ui2 = pcall(require, "vim._core.ui2")
if _ui2_ok then
  local _en_ok = pcall(_ui2.enable, { msg = { target = "msg" } })
  if _en_ok then
    vim.opt.cmdheight = 0
  else
    vim.opt.cmdheight = 1
  end
else
  vim.opt.cmdheight = 1
end
vim.opt.completeopt = "menu,menuone,noselect"
vim.opt.conceallevel = 2
vim.opt.confirm = true
vim.opt.cursorline = true
vim.opt.expandtab = true
vim.opt.foldlevel = 99
vim.opt.foldmethod = "indent"
vim.opt.ignorecase = true
vim.opt.inccommand = "nosplit"
vim.opt.laststatus = 3
vim.opt.linebreak = true
vim.opt.list = true
vim.opt.mouse = "a"
vim.opt.number = true
vim.opt.pumheight = 10
vim.opt.relativenumber = true
vim.opt.scrolloff = 8
vim.opt.scroll = 10
vim.opt.shiftwidth = 4
vim.opt.smartcase = true
vim.opt.smartindent = true
vim.opt.splitbelow = true
vim.opt.splitright = true
vim.opt.tabstop = 4
vim.opt.termguicolors = true
vim.opt.timeoutlen = 300
vim.opt.undofile = true
vim.opt.undolevels = 10000
vim.opt.updatetime = 200
vim.opt.wrap = false
vim.opt.signcolumn = "yes"
vim.opt.sessionoptions = { "buffers", "curdir", "tabpages", "winsize", "help", "globals", "skiprtp", "folds" }

vim.g.loaded_python3_provider = 0
vim.g.root_spec = { "cwd" }

-- Word-level inline diff (Neovim 0.12+): highlight only the changed characters
-- on reworded lines instead of washing the whole line in a neutral DiffChange.
-- Gives delta/GitHub-style precision in diffview and :diffsplit. Guarded with
-- pcall because the `inline:` value errors on <0.12.
pcall(function()
  vim.opt.diffopt:append("inline:word")
end)

-- Solid fill for deleted/filler lines in diff mode (diffview, :diffsplit).
-- A "╱" fillchar renders the diagonal-stripe hatch over the DiffDelete
-- background; a space makes it a solid block - the clean fill codediff
-- shows. (codediff does its own rendering, so it's unaffected; this only
-- touches Neovim's native diff filler.)
vim.opt.fillchars:append({ diff = " " })
