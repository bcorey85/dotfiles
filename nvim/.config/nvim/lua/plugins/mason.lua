-- Mason + LSP/tool install pipeline.
--
-- mason-lspconfig is loaded as a dependency of nvim-lspconfig (plugins/lspconfig.lua),
-- so its ensure_installed runs right before config.lsp's vim.lsp.enable on the
-- first file open — preserving the old mason -> mason-lspconfig -> enable order.
-- mason-tool-installer (formatters/linters/DAP adapters) is independent of LSP
-- activation, so it loads on VeryLazy to install in the background after startup.
-- (:MasonUpdate is not a build hook — the registry is fetched lazily on first use.)
return {
  {
    "mason-org/mason.nvim",
    cmd = { "Mason", "MasonInstall", "MasonUpdate", "MasonUninstall", "MasonLog" },
    config = function()
      require("mason").setup({
        ui = {
          icons = {
            package_installed = "✓",
            package_pending = "➜",
            package_uninstalled = "✗",
          },
        },
      })
    end,
  },
  {
    "mason-org/mason-lspconfig.nvim",
    lazy = true, -- loaded via nvim-lspconfig's dependencies, not eagerly
    dependencies = { "mason-org/mason.nvim" },
    config = function()
      require("mason-lspconfig").setup({
        ensure_installed = require("config.servers"),
        automatic_enable = false,
      })
    end,
  },
  {
    "WhoIsSethDaniel/mason-tool-installer.nvim",
    event = "VeryLazy",
    dependencies = { "mason-org/mason.nvim" },
    config = function()
      require("mason-tool-installer").setup({
        ensure_installed = {
          "stylua",
          "prettier",
          "shfmt", -- shell formatter (conform: sh/bash); bashls has no formatting

          -- Python formatting/import-sorting is handled by ruff (installed via
          -- mason-lspconfig in config/servers.lua, used by conform.nvim as
          -- ruff_fix + ruff_format). black/isort removed — they conflicted.
          -- nvim-lint runners (see lua/plugins/nvim-lint.lua)
          "shellcheck",
          "markdownlint",
          "yamllint",
          -- DAP adapters (lua/plugins/dap.lua)
          "debugpy", -- Python debug adapter; dap-python points at its venv python
          "js-debug-adapter", -- JS/TS debug adapter (pwa-node); used by dap.lua
        },
        auto_update = false,
        run_on_start = true,
      })
    end,
  },
}
