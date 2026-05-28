-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here

-- Load clipboard configuration
require("config.clipboard")

-- Keep cursor centered with padding
vim.opt.scrolloff = 8

-- Smaller scroll distance for C-d/C-u (default is half screen)
vim.opt.scroll = 10
vim.g.loaded_python3_provider = 0

vim.g.root_spec = { "cwd" }

-- Disable inlay hints by default (toggle with <leader>ih)
vim.g.lazyvim_inlay_hints = false

-- Word-level inline diff (Neovim 0.12+): highlight only the changed characters
-- on reworded lines instead of washing the whole line in a neutral DiffChange.
-- Gives delta/GitHub-style precision in diffview and :diffsplit. Guarded with
-- pcall because the `inline:` value errors on <0.12.
pcall(function()
  vim.opt.diffopt:append("inline:word")
end)

-- Solid fill for deleted/filler lines in diff mode (diffview, :diffsplit).
-- LazyVim defaults fillchars `diff` to "╱", which renders the diagonal-stripe
-- hatch over the DiffDelete background. A space makes it a solid block - the
-- clean fill codediff shows. (codediff does its own rendering, so it's
-- unaffected; this only touches Neovim's native diff filler.)
vim.opt.fillchars:append({ diff = " " })
