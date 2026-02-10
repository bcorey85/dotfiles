return {
  "lewis6991/gitsigns.nvim",
  opts = {
    current_line_blame = true,
    current_line_blame_opts = {
      delay = 200,
      virt_text_pos = "eol",
    },
  },
  keys = {
    { "<leader>ghd", function() require("gitsigns").diff_this() end, desc = "Diff This (Hunk)" },
    -- clear LazyVim's default <leader>gd so diffview owns it
    { "<leader>gd", false },
  },
}
