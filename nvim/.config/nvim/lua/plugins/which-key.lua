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
      { "<leader>c", group = "code" },
      { "<leader>d", group = "diff" },
      { "<leader>f", group = "file/find" },
      { "<leader>g", group = "git" },
{ "<leader>i", group = "inlay hints" },

      { "<leader>n", group = "notes (obsidian)" },
      { "<leader>q", group = "quit" },
      { "<leader>s", group = "search" },
      { "<leader>w", group = "windows" },
      { "<leader>x", group = "diagnostics/qf" },
      { "<leader>y", group = "yank" },
      { "g", group = "goto" },
      { "[", group = "prev" },
      { "]", group = "next" },
    })
  end,
}
