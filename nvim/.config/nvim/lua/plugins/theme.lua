return {
  -- Configure tokyonight theme
  {
    "folke/tokyonight.nvim",
    lazy = false,
    priority = 1000,
    opts = {
      style = "night", -- storm, moon, night, day
      transparent = false,
      styles = {
        sidebars = "dark",
        floats = "dark",
      },
    },
    config = function(_, opts)
      require("tokyonight").setup(opts)
      vim.cmd([[colorscheme tokyonight-night]])
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
