return {
  src = "stevearc/conform.nvim",
  setup = function()
    require("conform").setup({
      formatters_by_ft = {
        lua = { "stylua" },
        -- Mirror the repo's pre-commit (ruff-check --fix → ruff-format) so a
        -- saved buffer is already commit-clean. ruff reads pyproject.toml
        -- (e.g. line-length = 120) and owns import sorting via the I rules —
        -- black (wraps at 88) + isort would fight it and churn the diff.
        python = { "ruff_fix", "ruff_format" },
        javascript = { "prettier" },
        javascriptreact = { "prettier" },
        typescript = { "prettier" },
        typescriptreact = { "prettier" },
        vue = { "prettier" },
        css = { "prettier" },
        scss = { "prettier" },
        html = { "prettier" },
        json = { "prettier" },
        jsonc = { "prettier" },
        yaml = { "prettier" },
        markdown = { "prettier" },
      },
      format_on_save = {
        timeout_ms = 3000,
        lsp_fallback = true,
      },
    })

    vim.keymap.set("n", "<leader>cf", function()
      require("conform").format({ async = true, lsp_fallback = true })
    end, { desc = "Format buffer (conform)" })
  end,
}
