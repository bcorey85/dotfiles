-- gitsigns.nvim — git signs, hunk navigation, in-buffer staging/unstaging,
-- and a repo-wide quickfix list of hunks.
--
-- Division of responsibilities in this config:
--   gitsigns  → signs in the sign column, first/last hunk jumps (]H/[H), in-file
--               staging (- and the <leader>c* "changes" namespace), real diff
--               split (<leader>gd diffthis), hunk quickfix list (<leader>cq repo / <leader>cQ buffer)
--   keymaps   → next/prev hunk nav (]c/[c) and the = whole-file inline-diff toggle
--   neogit    → status buffer, transient popups (commit/push/pull/rebase/branch), history
--   util/merge → plugin-free conflict resolution for files with raw markers
--
-- Full code-review workflow cheatsheet: see the header of plugins/neogit.lua.
--
-- No preview_config.border is set here — vim.o.winborder = "rounded" in
-- options.lua already covers all floats globally (Neovim 0.11+).
return {
  src = "lewis6991/gitsigns.nvim",
  setup = function()
    require("gitsigns").setup({
      signs = {
        add = { text = "▎" },
        change = { text = "▎" },
        delete = { text = "▎" },
        topdelete = { text = "▎" },
        changedelete = { text = "▎" },
        untracked = { text = "▎" },
      },
      -- Show a second set of signs for hunks that are already staged, so you
      -- can see staged vs. unstaged state at a glance in the sign column.
      signs_staged_enable = true,
      signs_staged = {
        add = { text = "▎" },
        change = { text = "▎" },
        delete = { text = "▎" },
        topdelete = { text = "▎" },
        changedelete = { text = "▎" },
      },
      -- Persistent current-line blame: GitLens-style virtual text at end of the
      -- line under the cursor (author, relative time, summary), updating as the
      -- cursor moves. Toggle on/off with <leader>gB. The full-buffer blame split
      -- stays on neogit's `B` BranchPopup (`<leader>gg` then `B`). Formatter left at the gitsigns default
      -- (" <author>, <author_time:%R> - <summary> "; %R = relative time).
      current_line_blame = true,
      current_line_blame_opts = {
        virt_text = true,
        virt_text_pos = "eol",
        -- ms after the cursor settles before blame appears; low enough to feel
        -- persistent without flickering while scrolling through lines.
        delay = 300,
        ignore_whitespace = false,
      },
    })

    -- mode defaults to "n" when omitted; pass an explicit mode string for
    -- visual mappings.
    local map = function(lhs, rhs, desc, mode)
      vim.keymap.set(mode or "n", lhs, rhs, { desc = desc })
    end

    -- Hunk first/last jumps. Next/prev hunk nav lives on ]c/[c (keymaps.lua) —
    -- native diff-mode aware and centered; these capital-H variants jump to the
    -- first/last hunk in the buffer. target="all" keeps staged hunks in range:
    -- nav_hunk defaults to "unstaged", so without it a hunk drops out the moment
    -- you stage it (signs_staged_enable, set above, tracks the staged set).
    map("]H", function()
      require("gitsigns").nav_hunk("last", { target = "all" })
    end, "Last hunk")
    map("[H", function()
      require("gitsigns").nav_hunk("first", { target = "all" })
    end, "First hunk")

    -- Hunk preview float — quick single-hunk peek without leaving the buffer.
    -- (Whole-file inline overlay is the `=` key in keymaps.lua.)
    map("<leader>gD", function()
      require("gitsigns").preview_hunk()
    end, "Preview hunk (float)")

    -- <leader>gd ("git diff"): a REAL two-buffer diff split (working tree vs
    -- index) via :Gitsigns diffthis. Unlike the `=` inline overlay — whose
    -- removed lines are virtual lines the cursor can't enter, so j/k skip the
    -- whole block — both sides here are real buffers: j/k step line-by-line and
    -- ]c/[c, dp/do work. Use `=` to read a change in context; use this when you
    -- need to navigate or operate on the old/new lines. :q closes the split.
    map("<leader>gd", function()
      require("gitsigns").diffthis()
    end, "Diff this (real split, navigable)")

    -- Toggle the persistent current-line blame virtual text. neogit's
    -- `B` BranchPopup (open via <leader>gg) covers branch ops; <leader>gB is the
    -- inline current-line blame toggle. (Full-buffer blame split: `gb` in
    -- neogit's status buffer.)
    map("<leader>gB", function()
      require("gitsigns").toggle_current_line_blame()
    end, "Toggle line blame (inline)")

    -- Staging/unstaging — <leader>c* "changes" namespace.
    --
    -- stage_hunk TOGGLES: calling it on a hunk that is already staged will
    -- unstage it. There is no separate "unstage hunk" binding needed for that.
    map("<leader>cs", function()
      require("gitsigns").stage_hunk()
    end, "Stage/unstage hunk")
    -- Visual: stage only the selected lines within a hunk.
    map("<leader>cs", function()
      require("gitsigns").stage_hunk({ vim.fn.line("."), vim.fn.line("v") })
    end, "Stage/unstage hunk (range)", "v")

    -- `-` stages the hunk under the cursor (fires <leader>ghs / stage_hunk) for a
    -- fast ]c → - → ]c → - review loop. It only hijacks `-` when the cursor sits
    -- inside an unstaged hunk; anywhere else it replays the built-in `-` motion
    -- (first non-blank of the previous line), count included. Unstaging stays on
    -- <leader>cs (toggle) and <leader>cU — get_hunks only reports unstaged
    -- hunks, so the fallthrough can't see staged ones to toggle them back.
    map("-", function()
      local ok, gs = pcall(require, "gitsigns")
      if ok and not vim.wo.diff then
        local row = vim.fn.line(".")
        for _, h in ipairs(gs.get_hunks() or {}) do
          local s = h.added.start
          local e = s + math.max(h.added.count, 1) - 1
          if row >= s and row <= e then
            gs.stage_hunk()
            return
          end
        end
      end
      local count = vim.v.count > 0 and tostring(vim.v.count) or ""
      vim.api.nvim_feedkeys(count .. "-", "n", false) -- not on a hunk: native motion
    end, "Stage hunk on a change, else - motion")

    -- `_` UNSTAGES the staged hunk under the cursor — the safe inverse of `-`
    -- (stage), for a fast ]c → - (accept) / ]c → _ (pull back) review loop.
    -- gitsigns' stage_hunk() is a toggle: called on a staged hunk it inverts to
    -- unstage, preserving the working-tree change (only the index entry is
    -- dropped — non-destructive, unlike reset_hunk). The public get_hunks()
    -- reports UNSTAGED hunks only, so we read the staged set straight from the
    -- cache to fire ONLY when a staged hunk sits under the cursor; off one, `_`
    -- replays its native motion. To DISCARD a change outright (destructive),
    -- use <leader>cr — deliberately not on a bare key.
    map("_", function()
      local ok, gs = pcall(require, "gitsigns")
      if ok and not vim.wo.diff then
        local ok2, on_staged = pcall(function()
          local bcache = require("gitsigns.cache").cache[vim.api.nvim_get_current_buf()]
          local row = vim.fn.line(".")
          for _, h in ipairs(bcache and bcache.hunks_staged or {}) do
            local s = h.added.start
            local e = s + math.max(h.added.count, 1) - 1
            if row >= s and row <= e then
              return true
            end
          end
          return false
        end)
        if ok2 and on_staged then
          gs.stage_hunk() -- toggle → unstages the staged hunk under the cursor
          return
        end
      end
      local count = vim.v.count > 0 and tostring(vim.v.count) or ""
      vim.api.nvim_feedkeys(count .. "_", "n", false) -- not on a staged hunk: native motion
    end, "Unstage staged hunk under cursor, else _ motion")

    -- reset_hunk discards the working-tree change (irreversible for unsaved
    -- edits — the hunk is simply dropped, not staged).
    map("<leader>cr", function()
      require("gitsigns").reset_hunk()
    end, "Reset hunk")
    -- Visual: discard only the selected lines.
    map("<leader>cr", function()
      require("gitsigns").reset_hunk({ vim.fn.line("."), vim.fn.line("v") })
    end, "Reset hunk (range)", "v")

    -- Whole-buffer operations.
    map("<leader>cS", function()
      require("gitsigns").stage_buffer()
    end, "Stage buffer")
    map("<leader>cU", function()
      -- reset_buffer_index unstages all staged hunks in the buffer (index →
      -- HEAD), leaving the working-tree untouched.
      require("gitsigns").reset_buffer_index()
    end, "Unstage buffer (reset index)")
    map("<leader>cR", function()
      -- DESTRUCTIVE: reset_buffer discards ALL working-tree changes in the
      -- buffer, reverting to the last commit. Cannot be undone.
      require("gitsigns").reset_buffer()
    end, "Reset buffer (discard all — destructive)")

    -- Hunk quickfix lists (native qf, rendered by quicker.nvim).
    --
    -- <leader>cq is the headline feature: dumps every modified hunk across
    -- every file in the repo into the quickfix list. Navigate with ]q/[q as
    -- usual; `>` in the qf window expands diff context around each entry.
    --
    -- NOTE: the list goes stale as soon as you stage or reset a hunk because
    -- gitsigns recalculates line numbers after each change. Re-run <leader>cq
    -- to rebuild it after a staging session.
    -- Body lives in a user command so it's reusable from outside a keymap: the
    -- <leader>cq map calls it, and the `prefix s` tmux popup boots straight into
    -- it via `nvim -c GitHunksQf`, skipping neogit's status buffer entirely.
    vim.api.nvim_create_user_command("GitHunksQf", function()
      require("gitsigns").setqflist("all", {}, function()
        -- setqflist("all") is repo-wide and includes whole-file deletions
        -- (gitsigns emits a single "Removed" hunk for a `git rm`'d file). Those
        -- are dead entries in the review walk: the file is gone from disk, the
        -- deletion is already staged, and ]q into it just opens an empty buffer.
        -- Drop any item whose file no longer exists; partial removals inside
        -- still-present files keep their (existing) path and stay. Re-set the
        -- list with the title in one "r" (replace) call.
        local kept = vim.tbl_filter(function(it)
          local name = it.filename
          if (not name or name == "") and it.bufnr and it.bufnr > 0 then
            name = vim.api.nvim_buf_get_name(it.bufnr)
          end
          return name and name ~= "" and vim.uv.fs_stat(name) ~= nil
        end, vim.fn.getqflist())
        vim.fn.setqflist({}, "r", { title = "Gitsigns Hunks", items = kept })

        -- In the `prefix s` tmux popup, `q` in the qf window quits the throwaway
        -- nvim so the popup dismisses like lazygit. Set it here — after the qf
        -- window exists and quicker has run — via vim.schedule so this
        -- buffer-local map is the last writer and wins over quicker's `q`.
        if vim.env.GIT_QF_POPUP ~= nil then
          vim.schedule(function()
            for _, win in ipairs(vim.api.nvim_list_wins()) do
              local buf = vim.api.nvim_win_get_buf(win)
              if vim.bo[buf].filetype == "qf" then
                vim.keymap.set("n", "q", "<cmd>qa<cr>", { buffer = buf, desc = "Close git qf popup" })
              end
            end
          end)
        end
      end)
    end, { desc = "Repo-wide gitsigns hunk quickfix list" })

    map("<leader>cq", "<cmd>GitHunksQf<cr>", "Hunk qf list (repo-wide)")

    -- Current buffer only — focused "what did I change here?" scan. Capital Q
    -- pairs with the more-used repo-wide <leader>cq.
    map("<leader>cQ", function()
      require("gitsigns").setqflist(0, {}, function()
        -- Same title as <leader>cq for a consistent qf header.
        vim.fn.setqflist({}, "a", { title = "Gitsigns Hunks" })
      end)
    end, "Hunk qf list (buffer)")
  end,
}
