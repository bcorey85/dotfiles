return {
  "linrongbin16/gitlinker.nvim",
  cmd = "GitLink",
  opts = {},
  keys = {
    { "<leader>yg", "<cmd>GitLink<cr>", mode = { "n", "v" }, desc = "Yank git permalink" },
    { "<leader>go", "<cmd>GitLink!<cr>", mode = { "n", "v" }, desc = "Open git permalink in browser" },
  },
}
