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
vim.opt.shortmess:append("I")
vim.opt.showcmdloc = "statusline"
vim.opt.completeopt = "menu,menuone,noselect"
vim.opt.conceallevel = 2
vim.opt.confirm = true
vim.opt.cursorline = false
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
-- "split" opens a preview pane listing EVERY :s match (off-screen included)
-- while typing — the native stand-in for grug-far's streaming preview.
vim.opt.inccommand = "split"
vim.opt.laststatus = 3
vim.opt.linebreak = true
vim.opt.list = true
vim.opt.mouse = "a"
vim.opt.number = true
vim.opt.pumheight = 10
vim.opt.relativenumber = true
vim.opt.scrolloff = 4
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
vim.opt.wrap = true
vim.opt.signcolumn = "yes"

vim.g.loaded_python3_provider = 0
vim.g.loaded_node_provider = 0
vim.g.loaded_perl_provider = 0
vim.g.loaded_ruby_provider = 0

-- Global float border style (Neovim 0.11+): all floats (LSP hover, signature
-- help, diagnostic floats, which-key, tiny-cmdline) inherit this one setting.
-- Guarded with pcall because vim.o.winborder does not exist on 0.10 and would
-- error without the guard.
pcall(function()
  vim.o.winborder = "rounded"
end)

-- Word-level inline diff (Neovim 0.12+): highlight only the changed WORDS on
-- reworded lines instead of washing the whole line in a neutral DiffChange.
-- Gives delta/GitHub-style precision in :diffsplit and native diff mode. Guarded with
-- pcall because the `inline:` value errors on <0.12.
--
-- The `:remove` is load-bearing: Neovim 0.12 ships `inline:char` in the DEFAULT
-- diffopt, and a bare `:append("inline:word")` leaves BOTH present with char
-- winning — so changed lines render chopped per-CHARACTER (e.g. `P r e p`),
-- especially in misaligned 3-way merge views. Drop the default first.
pcall(function()
  vim.opt.diffopt:remove("inline:char")
  vim.opt.diffopt:append("inline:word")
end)

-- Solid fill for deleted/filler lines in diff mode (:diffsplit, native diff).
-- A "╱" fillchar renders the diagonal-stripe hatch over the DiffDelete
-- background; a space makes it a solid block - the clean fill codediff
-- shows. (codediff does its own rendering, so it's unaffected; this only
-- touches Neovim's native diff filler.)
vim.opt.fillchars:append({ diff = " " })

-- :grep / :copen quickfix searches get the same visibility as the snacks
-- pickers (hidden files, gitignored dotfiles, junk-dir excludes). Exclusion
-- globs come from util.search — single source of truth shared with the picker.
-- Single-quote each glob: :grep runs grepprg through the shell, and zsh expands
-- unquoted `!`/`*` itself (erroring "no matches found" on a miss, unlike bash);
-- quotes make zsh hand them to rg. (Relocated here from the old mini-pick.lua.)
do
  local globs = {}
  for _, pat in ipairs(require("util.search").exclude_patterns()) do
    table.insert(globs, "--glob='!" .. pat .. "'")
  end
  vim.o.grepprg = "rg --vimgrep --smart-case --hidden --no-ignore-vcs " .. table.concat(globs, " ")
  vim.o.grepformat = "%f:%l:%c:%m"
end

vim.opt.showtabline = 0
