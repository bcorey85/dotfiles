-- Auto-pairs (mini.pairs, from the mini.nvim monorepo) + auto-close/rename HTML
-- and JSX tags (nvim-ts-autotag).
return {
  {
    src = "echasnovski/mini.nvim",
    setup = function()
      require("mini.pairs").setup({
        modes = { insert = true, command = true, terminal = false },
      })
    end,
  },
  {
    src = "windwp/nvim-ts-autotag",
    setup = function()
      require("nvim-ts-autotag").setup({})
    end,
  },
}
