return {
  {
    "olimorris/onedarkpro.nvim",
    lazy = false,
    priority = 1000,
    config = function(_, opts)
      vim.cmd([[colorscheme onedark]])
    end,
  },
}
