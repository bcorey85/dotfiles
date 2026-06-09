-- Ships the lsp/*.lua server definitions (cmd, root_markers, filetypes) that
-- config/lsp.lua's vim.lsp.config / vim.lsp.enable build on. No setup() — it's
-- consumed declaratively via the runtimepath by config.lsp (required at the end
-- of pack.lua).
return {
  src = "neovim/nvim-lspconfig",
}
