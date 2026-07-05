-- Ships the lsp/*.lua server definitions (cmd, root_markers, filetypes) that
-- config/lsp.lua's vim.lsp.config / vim.lsp.enable build on.
--
-- config.lsp reads vim.lsp.config.eslint.root_dir, so it REQUIRES this plugin on
-- the runtimepath before it runs — hence config.lsp is invoked from THIS spec's
-- config() rather than at top level. Gated on BufReadPre so servers still
-- activate lazily on the first file open (vim.lsp.enable registers FileType
-- autocmds that catch the buffer being read). mason-lspconfig is a dependency so
-- ensure_installed runs before vim.lsp.enable, preserving the old load order.
return {
  "neovim/nvim-lspconfig",
  event = { "BufReadPre", "BufNewFile" },
  dependencies = { "mason-org/mason-lspconfig.nvim" },
  config = function()
    require("config.lsp")
  end,
}
