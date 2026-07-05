-- Context-aware commentstring for the built-in gc/gcc (embedded langs: JSX,
-- Vue templates, etc.).
return {
  "folke/ts-comments.nvim",
  event = "VeryLazy",
  config = function()
    require("ts-comments").setup({})
  end,
}
