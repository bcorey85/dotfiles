return {
  "nvim-treesitter/nvim-treesitter-context",
  event = { "BufReadPost", "BufNewFile" },
  opts = {
    max_lines = 3,
    min_window_height = 20,
    multiline_threshold = 1,
    trim_scope = "outer",
    mode = "cursor",
    separator = "─",
  },
  keys = {
    {
      "<leader>uc",
      function() require("treesitter-context").toggle() end,
      desc = "Toggle treesitter context",
    },
    {
      "[x",
      function() require("treesitter-context").go_to_context(vim.v.count1) end,
      desc = "Jump to context (upwards)",
    },
  },
}
