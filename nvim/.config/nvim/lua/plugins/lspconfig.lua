-- Ships the lsp/*.lua server definitions (cmd, root_markers, filetypes) that
-- config/lsp.lua's vim.lsp.config / vim.lsp.enable build on.
--
-- config.lsp reads vim.lsp.config.eslint.root_dir, so it REQUIRES this plugin on
-- the runtimepath before it runs — hence config.lsp is invoked from THIS spec's
-- config() rather than at top level. mason-lspconfig is a dependency so
-- ensure_installed runs before vim.lsp.enable, preserving the old load order.
--
-- Trigger is VeryLazy, NOT BufReadPre: vim.lsp.enable() called after VimEnter
-- runs `doautoall nvim.lsp.enable FileType`, which sets the global
-- did_filetype() flag. On BufReadPre that fired MID-READ of the first buffer
-- (session restore / first file open), so the read's own `setf` no-op'd and the
-- buffer got NO filetype — no treesitter/markview/spell until :e. VeryLazy runs
-- after startup+restore finish; the doautoall sweep then attaches LSP to every
-- already-open buffer, so first-buffer LSP still works.
return {
  "neovim/nvim-lspconfig",
  event = "VeryLazy",
  dependencies = { "mason-org/mason-lspconfig.nvim" },
  config = function()
    require("config.lsp")
  end,
}
