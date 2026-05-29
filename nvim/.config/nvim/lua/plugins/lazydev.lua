return {
  {
    "folke/lazydev.nvim",
    ft = "lua",
    opts = {
      library = {
        -- Load luvit types when the `vim.uv` word is found
        { path = "${3rd}/luv/library", words = { "vim%.uv" } },
        -- Snacks types when `Snacks` is referenced
        { path = "snacks.nvim", words = { "Snacks" } },
      },
    },
  },
}
