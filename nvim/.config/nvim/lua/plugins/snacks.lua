return {
  "folke/snacks.nvim",
  opts = {
    dashboard = { enabled = false },
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
          ignored = false,
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
