-- Inline ghost text only. Accept is <C-j>, not <Tab>, because blink.cmp's
-- super-tab preset already owns <Tab> in insert mode.
return {
  "supermaven-inc/supermaven-nvim",
  enabled = false,
  event = "InsertEnter",
  opts = {
    keymaps = {
      accept_suggestion = "<C-j>",
      clear_suggeetion = "<C-]>",
      accept_word = "<C-l>",
    },
  },
}
