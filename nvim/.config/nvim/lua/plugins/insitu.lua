-- insitu.nvim — repo-wide navigation across unreviewed git hunks.
-- Source: github.com/bcorey85/insitu.nvim (private)
--
-- Navigation, plus the two verbs that drain its queue (accept/reject) for the
-- cases gitsigns can't see -- untracked files have no hunk to stage. The
-- bindings stay where they already are:
--   -           stage hunk under cursor, or accept a new file
--               (plugins/gitsigns.lua; the untracked branch calls insitu)
--   _           unstage staged hunk          (plugins/gitsigns.lua)
--   =           toggle inline diff overlay   (config/keymaps.lua)
--   <leader>cr  discard hunk, or delete a new file (prompts)
--
--   ]c / [c  → next/prev hunk in THIS BUFFER (existing, gitsigns)
--   ]r / [r  → next/prev unstaged hunk, repo-wide
--   ]R / [R  → next/prev staged hunk, repo-wide
--
-- Three grains, coarse to fine, none of which leave the editor:
--   <leader>rr  which files changed  → lands in the real file
--   ]r          which hunks changed  → lands at the change, file around it
--   =           what changed here    → overlay, on demand
-- neogit (`prefix g`) stays for commit composition, not for reading.
return {
  "bcorey85/insitu.nvim",
  -- Private repo: lazy clones over HTTPS by default, which can't authenticate
  -- (and can't prompt — `terminal prompts disabled`). Force the SSH remote for
  -- this plugin only, leaving every other plugin on HTTPS.
  url = "git@github.com:bcorey85/insitu.nvim.git",
  dependencies = { "lewis6991/gitsigns.nvim" },
  -- plugin/insitu.lua defines these, but a lazy-loaded plugin's plugin/ files
  -- don't run until it loads — so `nvim -c "InsituNext"` (the prefix G popup)
  -- would hit E492 without lazy stubbing the command here.
  cmd = { "InsituNext", "InsituPrev", "InsituNextStaged", "InsituPrevStaged", "InsituStatus" },
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
    {
      -- The coarse grain, and the reason `prefix g` -> neogit isn't needed to
      -- start a review: <CR> opens the REAL file (preview shows the diff, the
      -- open does not), untracked files included. <Tab> stages, <C-r> restores.
      "<leader>rr",
      function()
        require("snacks").picker.git_status()
      end,
      desc = "Changed files (repo-wide)",
    },
  },
  config = function()
    -- Warms the index stat cache: `git diff` refreshes the index in memory but
    -- never writes it back, so on a cold repo every call re-hashes the worktree
    -- (87ms vs 2.3ms measured). `git status` does persist it.
    require("insitu").setup()
  end,
}
