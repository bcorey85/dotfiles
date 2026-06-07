return {
  "mbbill/undotree",
  cmd = "UndotreeToggle",
  keys = {
    { "<leader>uu", "<cmd>UndotreeToggle<cr>", desc = "Undotree (toggle)" },
  },
  init = function()
    vim.g.undotree_WindowLayout = 2
    vim.g.undotree_SetFocusWhenToggle = 1
    vim.g.undotree_SplitWidth = 36
  end,
}
