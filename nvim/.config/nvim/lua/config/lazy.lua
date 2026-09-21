-- lazy.nvim bootstrap.
--
-- LSP: config.lsp reads vim.lsp.config.eslint.root_dir, so it REQUIRES
-- nvim-lspconfig on the rtp. It runs from the lspconfig spec's config()
-- (plugins/lspconfig.lua), gated on BufReadPre — not here — so servers still
-- activate lazily on file open.

local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  local out = vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "--branch=stable",
    "https://github.com/folke/lazy.nvim.git",
    lazypath,
  })
  if vim.v.shell_error ~= 0 then
    error("Failed to clone lazy.nvim:\n" .. out)
  end
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  spec = { { import = "plugins" } },
  install = { colorscheme = { "onedark" } },
  checker = { enabled = false }, -- no background update checks
  change_detection = { enabled = false }, -- don't watch/reload spec files
  ui = { border = "rounded" },
  performance = {
    rtp = {
      disabled_plugins = {
        "gzip",
        "tarPlugin",
        "tohtml",
        "tutor",
        "zipPlugin",
        "netrwPlugin",
      },
    },
  },
})

-- Must stay here, not in a plugin spec: the eager colorscheme spec is already
-- on the rtp by this line, and start() must run exactly once.
require("config.theme-sync").start()

-- Convenience: keep muscle-memory for the old pack commands pointing at lazy.
vim.api.nvim_create_user_command("PackUpdate", "Lazy update", { desc = "(compat) -> Lazy update" })
vim.api.nvim_create_user_command("PackStatus", "Lazy", { desc = "(compat) -> Lazy" })
vim.api.nvim_create_user_command("PackClean", "Lazy clean", { desc = "(compat) -> Lazy clean" })
