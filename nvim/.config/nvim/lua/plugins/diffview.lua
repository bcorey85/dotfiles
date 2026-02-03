return {
  "sindrets/diffview.nvim",
  cmd = { "DiffviewOpen", "DiffviewFileHistory" },
  keys = {
    { "<leader>gd", "<cmd>DiffviewOpen<cr>", desc = "Diff View" },
    { "<leader>gD", "<cmd>DiffviewClose<cr>", desc = "Close Diff View" },
    { "<leader>gH", "<cmd>DiffviewFileHistory<cr>", desc = "File History" },
  },
}
