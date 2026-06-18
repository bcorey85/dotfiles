-- Auto-pairs (mini.pairs, from the mini.nvim monorepo) + auto-close/rename HTML
-- and JSX tags (nvim-ts-autotag).
return {
  {
    src = "echasnovski/mini.nvim",
    setup = function()
      -- command-mode pairs are off: auto-inserting a closing )/}/] mid-pattern
      -- fights regex/substitution typing (:%s/(foo)/(bar)/, :g/{/). Insert mode
      -- keeps pairs; terminal stays off so they don't interfere with the shell.
      require("mini.pairs").setup({
        modes = { insert = true, command = false, terminal = false },
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
