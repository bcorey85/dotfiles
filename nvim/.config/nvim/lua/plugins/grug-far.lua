return {
  src = "MagicDuck/grug-far.nvim",
  setup = function()
    require("grug-far").setup({ headerMaxWidth = 80 })

    vim.keymap.set("n", "<leader>sr", function()
      require("grug-far").open()
    end, { desc = "Search and Replace" })
  end,
}
