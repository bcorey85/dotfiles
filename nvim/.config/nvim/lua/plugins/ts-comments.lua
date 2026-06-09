-- Context-aware commentstring for the built-in gc/gcc (embedded langs: JSX,
-- Vue templates, etc.).
return {
  src = "folke/ts-comments.nvim",
  setup = function()
    require("ts-comments").setup({})
  end,
}
