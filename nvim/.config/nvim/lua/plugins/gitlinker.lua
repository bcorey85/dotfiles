return {
  src = "linrongbin16/gitlinker.nvim",
  setup = function()
    require("gitlinker").setup({})

    vim.keymap.set({ "n", "v" }, "<leader>yg", "<cmd>GitLink<cr>", { desc = "Yank git permalink" })
    vim.keymap.set({ "n", "v" }, "<leader>go", "<cmd>GitLink!<cr>", { desc = "Open git permalink in browser" })
  end,
}
