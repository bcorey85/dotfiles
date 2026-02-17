-- return {
--   {
--     "sainnhe/sonokai",
--     lazy = false,
--     priority = 1000,
--     config = function()
--       vim.g.sonokai_style = "maia"
--       vim.cmd.colorscheme("sonokai")
--       vim.api.nvim_set_hl(0, "Directory", { fg = "#e3e1e4" })
--       vim.api.nvim_set_hl(0, "MiniIconsAzure", { fg = "#9ecd6f" })
--     end,
--   },
-- }
return {
  {
    "everviolet/nvim",
    name = "evergarden",
    lazy = false,
    priority = 1000,
    config = function(_, opts)
      require("evergarden").setup(opts)
      vim.cmd.colorscheme("evergarden")
    end,
    opts = {
      theme = {
        variant = "fall",
        accent = "green",
      },
    },
  },
}
