return {
  "folke/snacks.nvim",
  opts = {
    picker = {
      sources = {
        explorer = {
          hidden = true,
          ignored = true,
        },
        files = {
          hidden = true,
          ignored = true,
          follow = true,
        },
        grep = {
          hidden = true,
          ignored = true,
          follow = true,
        },
      },
    },
  },
  keys = {
    {
      "<leader>fI",
      function()
        Snacks.picker.files({ hidden = true, ignored = true })
      end,
      desc = "Find files (including ignored)",
    },
  },
}
