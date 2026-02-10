return {
  "sindrets/diffview.nvim",
  cmd = { "DiffviewOpen", "DiffviewFileHistory" },
  keys = {
    { "<leader>gv", "<cmd>DiffviewOpen<cr>", desc = "Diff View" },
    { "<leader>gV", "<cmd>DiffviewClose<cr>", desc = "Close Diff View" },
    { "<leader>gH", "<cmd>DiffviewFileHistory<cr>", desc = "File History" },
  },
}
