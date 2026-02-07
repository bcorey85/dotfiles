return {
  {
    "folke/sidekick.nvim",
    opts = {
      nes = { enabled = false },
      cli = {
        mux = {
          backend = "tmux",
          enabled = true,
        },
        win = {
          split = {
            width = 60,
          },
        },
      },
    },
  },
}
