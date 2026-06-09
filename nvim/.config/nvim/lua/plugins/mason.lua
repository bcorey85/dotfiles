-- mason.setup() must run before the two consumers below; pack.lua preserves
-- this list order when collecting setups. (:MasonUpdate is no longer wired as a
-- build hook — the registry is fetched lazily on first use, and
-- mason-tool-installer's run_on_start handles tool installs.)
return {
  {
    src = "mason-org/mason.nvim",
    setup = function()
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
    src = "mason-org/mason-lspconfig.nvim",
    deps = { "mason-org/mason.nvim" },
    setup = function()
      require("mason-lspconfig").setup({
        ensure_installed = require("config.servers"),
        automatic_enable = false,
      })
    end,
  },
  {
    src = "WhoIsSethDaniel/mason-tool-installer.nvim",
    deps = { "mason-org/mason.nvim" },
    setup = function()
      require("mason-tool-installer").setup({
        ensure_installed = {
          "stylua",
          "prettier",
          "black",
          "isort",
          -- nvim-lint runners (see lua/plugins/nvim-lint.lua)
          "shellcheck",
          "markdownlint",
          "yamllint",
        },
        auto_update = false,
        run_on_start = true,
      })
    end,
  },
}
