return {
  {
    "folke/sidekick.nvim",
    opts = {
      cli = {
        win = {
          split = {
            width = 50,
          },
        },
      },
    },
  },
  {
    "saghen/blink.cmp",
    opts = {
      keymap = {
        ["<Tab>"] = {
          "snippet_forward",
          function()
            return require("sidekick").nes_jump_or_apply()
          end,
          "fallback",
        },
      },
    },
  },
}
