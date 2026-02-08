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
