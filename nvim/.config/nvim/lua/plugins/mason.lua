return {
  {
    "mason-org/mason.nvim",
    cmd = "Mason",
    build = ":MasonUpdate",
    opts = {
      ui = {
        icons = {
          package_installed = "✓",
          package_pending = "➜",
          package_uninstalled = "✗",
        },
      },
    },
  },
  {
    "mason-org/mason-lspconfig.nvim",
    dependencies = { "mason-org/mason.nvim" },
    opts = {
      ensure_installed = {
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
      },
      automatic_enable = false,
    },
  },
  {
    "WhoIsSethDaniel/mason-tool-installer.nvim",
    dependencies = { "mason-org/mason.nvim" },
    opts = {
      ensure_installed = {
        "stylua",
        "prettier",
        "black",
        "isort",
        "js-debug-adapter",
      },
      auto_update = false,
      run_on_start = true,
    },
  },
}
