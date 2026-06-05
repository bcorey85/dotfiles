return {
  "folke/snacks.nvim",
  priority = 1000,
  lazy = false,
  opts = {
    bigfile = { enabled = true },
    dashboard = { enabled = false },
    explorer = { enabled = false },
    indent = { enabled = true, scope = { enabled = false } }, -- active-scope line via mini.indentscope
    input = { enabled = true },
    notifier = {
      enabled = true,
      timeout = 3000,
    },
    picker = { enabled = false },
    quickfile = { enabled = true },
    scope = { enabled = true },
    scroll = { enabled = false },
    statuscolumn = { enabled = true },
    words = { enabled = true },
    lazygit = { enabled = false },
    styles = {
      notification = {},
    },
  },
  keys = {
    {
      "<leader>wm",
      function()
        Snacks.toggle.zoom():toggle()
      end,
      desc = "Toggle Zoom",
    },
  },
}
