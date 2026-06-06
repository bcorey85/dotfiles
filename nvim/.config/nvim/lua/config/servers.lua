-- Single source of truth for the managed LSP server list.
-- Consumed by config/lsp.lua (vim.lsp.enable) and plugins/mason.lua
-- (mason-lspconfig ensure_installed). Add or remove servers here only.
return {
  "vtsls",
  "vue_ls",
  "eslint",
  "lua_ls",
  "pyright",
  "ruff",
  "cssls",
  "html",
  "jsonls",
  "yamlls",
  "bashls",
  "ansiblels",
  "oxlint",
}
