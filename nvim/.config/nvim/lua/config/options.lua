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
-- With cmdheight=0 the native showcmd (pending count/operator, and the visual
-- selection size like 3x5 in visual-block) has no cmdline to render in. Route
-- it into the statusline instead, where the `%S` field in config/statusline.lua
-- displays it. showcmd itself is on by default.
vim.opt.showcmdloc = "statusline"
vim.opt.completeopt = "menu,menuone,noselect"
vim.opt.conceallevel = 2
vim.opt.confirm = true
vim.opt.cursorline = true
vim.opt.expandtab = true
vim.opt.foldlevel = 99
-- Treesitter-aware folds. foldexpr returns "0" for buffers with no parser, so
-- those simply don't fold (indent folding was marginal there anyway). Set
-- globally rather than per-FileType to avoid the known window-local fold leak
-- where wo options set in a FileType autocmd bleed into other buffers sharing
-- the window. foldtext="" opts into Neovim's syntax-highlighted fold text.
vim.opt.foldmethod = "expr"
vim.opt.foldexpr = "v:lua.vim.treesitter.foldexpr()"
vim.opt.foldtext = ""
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

-- Global float border style (Neovim 0.11+): all floats (LSP hover, signature
-- help, diagnostic floats, which-key, tiny-cmdline) inherit this one setting.
-- Guarded with pcall because vim.o.winborder does not exist on 0.10 and would
-- error without the guard.
pcall(function()
  vim.o.winborder = "rounded"
end)

-- Word-level inline diff (Neovim 0.12+): highlight only the changed characters
-- on reworded lines instead of washing the whole line in a neutral DiffChange.
-- Gives delta/GitHub-style precision in :Gdiffsplit and :diffsplit. Guarded with
-- pcall because the `inline:` value errors on <0.12.
pcall(function()
  vim.opt.diffopt:append("inline:word")
end)

-- Solid fill for deleted/filler lines in diff mode (:Gdiffsplit, :diffsplit).
-- A "╱" fillchar renders the diagonal-stripe hatch over the DiffDelete
-- background; a space makes it a solid block - the clean fill codediff
-- shows. (codediff does its own rendering, so it's unaffected; this only
-- touches Neovim's native diff filler.)
vim.opt.fillchars:append({ diff = " " })

vim.opt.showtabline = 0

-- hide default dashboard
vim.cmd("set shortmess+=I")
