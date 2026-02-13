return {
  "mikavilpas/yazi.nvim",
  event = "VeryLazy",
  keys = {
    { "<leader>y", "<cmd>Yazi<cr>", desc = "Open Yazi at current file" },
    { "<leader>Y", "<cmd>Yazi cwd<cr>", desc = "Open Yazi in cwd" },
  },
  opts = {
    open_for_directories = true,
  },
  init = function()
    vim.g.loaded_netrwPlugin = 1
  end,
}
