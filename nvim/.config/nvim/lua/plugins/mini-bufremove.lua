-- mini.bufremove — delete a buffer while preserving the window layout. From the
-- mini.nvim monorepo (shared clone).
return {
  src = "echasnovski/mini.nvim",
  setup = function()
    require("mini.bufremove").setup({})

    -- Delete the current buffer without disturbing the window layout. force=false
    -- so a modified buffer prompts instead of silently discarding changes.
    vim.keymap.set("n", "<leader>bb", function()
      require("mini.bufremove").delete(0, false)
    end, { desc = "Delete buffer" })
  end,
}
