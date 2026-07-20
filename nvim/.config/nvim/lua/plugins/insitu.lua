-- insitu.nvim — repo-wide navigation across unreviewed git hunks.
-- Source: github.com/bcorey85/insitu.nvim (private)
--
-- Navigation only. The verbs stay where they already are:
--   -           stage hunk under cursor      (plugins/gitsigns.lua)
--   _           unstage staged hunk          (plugins/gitsigns.lua)
--   =           toggle inline diff overlay   (config/keymaps.lua)
--   <leader>cr  discard hunk
--
--   ]c / [c  → next/prev hunk in THIS BUFFER (existing, gitsigns)
--   ]r / [r  → next/prev unstaged hunk, repo-wide
--   ]R / [R  → next/prev staged hunk, repo-wide
return {
  "bcorey85/insitu.nvim",
  -- Private repo: lazy clones over HTTPS by default, which can't authenticate
  -- (and can't prompt — `terminal prompts disabled`). Force the SSH remote for
  -- this plugin only, leaving every other plugin on HTTPS.
  url = "git@github.com:bcorey85/insitu.nvim.git",
  dependencies = { "lewis6991/gitsigns.nvim" },
  keys = {
    {
      "]r",
      function()
        require("insitu").next()
      end,
      desc = "Next unstaged hunk (repo-wide)",
    },
    {
      "[r",
      function()
        require("insitu").prev()
      end,
      desc = "Prev unstaged hunk (repo-wide)",
    },
    {
      "]R",
      function()
        require("insitu").next_staged()
      end,
      desc = "Next staged hunk (repo-wide)",
    },
    {
      "[R",
      function()
        require("insitu").prev_staged()
      end,
      desc = "Prev staged hunk (repo-wide)",
    },
    {
      "<leader>rs",
      function()
        require("insitu").status()
      end,
      desc = "Hunk counts (unstaged / staged)",
    },
    {
      "<leader>rf",
      function()
        require("snacks").picker.git_diff({ group = false })
      end,
      desc = "Find a hunk (fuzzy)",
    },
  },
  config = function()
    -- Warms the index stat cache: `git diff` refreshes the index in memory but
    -- never writes it back, so on a cold repo every call re-hashes the worktree
    -- (87ms vs 2.3ms measured). `git status` does persist it.
    require("insitu").setup()
  end,
}
