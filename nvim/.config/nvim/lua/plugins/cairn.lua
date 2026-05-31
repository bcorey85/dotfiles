return {
  "GooseRooster/cairn.nvim",
  event = "VeryLazy",
  config = function()
    require("cairn").setup({
      keymaps = {
        add = "<leader>ka",
        remove = "<leader>kd",
        picker = "<leader>kk",
        index_prefix = "<leader>k",
      },
    })
  end,
}
