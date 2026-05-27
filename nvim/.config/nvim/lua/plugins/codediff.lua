return {
  -- VSCode-style diff: side-by-side + inline, line- and character-level
  -- highlighting, using VSCode's diff algorithm compiled to C (prebuilt binary
  -- auto-downloaded on first use - no build step). The performance-oriented
  -- diffview competitor. Explorer panel with ]f / [f next/prev file.
  -- :CodeDiff (git status), :CodeDiff <rev>, :CodeDiff history.
  "esmuellert/codediff.nvim",
  cmd = "CodeDiff",
  keys = {
    { "<leader>cD", "<cmd>CodeDiff<cr>", desc = "CodeDiff review" },
  },
}
