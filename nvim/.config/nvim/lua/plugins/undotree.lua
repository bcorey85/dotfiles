-- undotree — visual navigator for Neovim's undo history.
-- undofile + undolevels=10000 are set in options.lua; this makes that
-- history visible and navigable as a tree rather than a linear stack.
return {
  "mbbill/undotree",
  keys = {
    { "<leader>uu", desc = "Undo tree" },
    { "<leader>su", desc = "Undo tree" },
  },
  cmd = { "UndotreeToggle", "UndotreeShow" },
  config = function()
    vim.g.undotree_SetFocusWhenToggle = 1

    vim.keymap.set("n", "<leader>uu", vim.cmd.UndotreeToggle, { desc = "Undo tree" })
    -- <leader>su mirrors Doom `SPC s u` (undo-tree-visualize).
    vim.keymap.set("n", "<leader>su", vim.cmd.UndotreeToggle, { desc = "Undo tree" })
  end,
}
