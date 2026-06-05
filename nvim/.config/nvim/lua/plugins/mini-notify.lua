-- mini.notify: toast notifications (replaces the old notifier plugin).
-- fidget.nvim owns LSP progress; lsp_progress is disabled here to avoid overlap.
return {
  {
    "echasnovski/mini.notify",
    event = "VeryLazy",
    config = function()
      require("mini.notify").setup({
        lsp_progress = { enable = false },
        window = { config = { border = "rounded" } },
      })
      vim.notify = require("mini.notify").make_notify({
        ERROR = { duration = 5000 },
        WARN = { duration = 4000 },
        INFO = { duration = 3000 },
      })
    end,
  },
}
