return {
  "folke/which-key.nvim",
  event = "VeryLazy",
  opts = {
    preset = "helix",
    delay = function(ctx)
      return ctx.plugin and 0 or 300
    end,
    icons = {
      mappings = true,
      colors = true,
    },
    win = {
      no_overlap = true,
      padding = { 1, 2 },
      title = true,
      title_pos = "center",
      wo = { winblend = 0 },
    },
  },
  config = function(_, opts)
    local wk = require("which-key")
    wk.setup(opts)

    wk.add({
      { "<leader>b", group = "buffer" },
      { "<leader>c", group = "code" },
      { "<leader>d", group = "debug" },
      { "<leader>f", group = "file/find" },
      { "<leader>g", group = "git" },
      { "<leader>gh", group = "github (octo)" },
      { "<leader>gr", group = "octo: review" },
      { "<leader>i", group = "inlay hints" },
      { "<leader>m", group = "markdown" },
      { "<leader>n", group = "notes (obsidian)" },
      { "<leader>o", group = "obsidian" },
      { "<leader>q", group = "quit/session" },
      { "<leader>s", group = "search" },
      { "<leader>t", group = "test" },
      { "<leader>w", group = "windows" },
      { "<leader>x", group = "diagnostics/qf" },
      { "<leader>y", group = "yank" },
      { "<leader>A", desc = "Multicursor: add cursors for all matches" },
      { "g", group = "goto" },
      { "[", group = "prev" },
      { "]", group = "next" },
    })
  end,
}
