return {
  {
    "AlexvZyl/nordic.nvim",
    lazy = false,
    priority = 1000,
    config = function(_, opts)
      vim.cmd([[colorscheme nordic]])
    end,
  },
}
