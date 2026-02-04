return {
  -- Configure tokyonight theme
  {
    "olimorris/onedarkpro.nvim",
    lazy = false,
    priority = 1000,
    config = function(_, opts)
      vim.cmd([[colorscheme onedark]])
    end,
  },

  -- Customize dashboard (splash screen)
  {
    "nvimdev/dashboard-nvim",
    opts = function(_, opts)
      -- Remove blue background
      opts.theme = "doom"
      opts.config = opts.config or {}
      opts.config.header = opts.config.header or {}

      -- Dashboard will use your colorscheme instead of blue background
      return opts
    end,
  },
}
