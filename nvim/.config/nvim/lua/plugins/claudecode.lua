return {
  "coder/claudecode.nvim",
  enabled = false,
  dependencies = { "folke/snacks.nvim" },
  keys = {
    { "<C-'>", "<cmd>ClaudeCodeFocus<cr>", desc = "Claude Code", mode = { "n", "x", "t" } },
    { "<leader>ac", "<cmd>ClaudeCode<cr>", desc = "Toggle Claude" },
    { "<leader>ar", "<cmd>ClaudeCode --resume<cr>", desc = "Resume Claude" },
    { "<leader>ab", "<cmd>ClaudeCodeAdd %<cr>", desc = "Add buffer to Claude" },
    { "<leader>as", "<cmd>ClaudeCodeSend<cr>", mode = "v", desc = "Send selection to Claude" },
    { "<leader>aa", "<cmd>ClaudeCodeDiffAccept<cr>", desc = "Accept diff" },
    { "<leader>ad", "<cmd>ClaudeCodeDiffDeny<cr>", desc = "Deny diff" },
  },
  opts = {
    terminal = {
      split_side = "right",
      split_width_percentage = 0.20,
      provider = "snacks",
      snacks_win_opts = {
        wo = {
          wrap = true,
          linebreak = true,
        },
      },
    },
    diff_opts = {
      auto_close_on_accept = true,
      vertical_split = true,
      show_native_diff = false,
      open_in_current_tab = false,
      keep_terminal_focus = true,
    },
  },
}
