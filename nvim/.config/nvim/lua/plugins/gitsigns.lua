-- gitsigns.nvim — git signs, hunk navigation, in-buffer staging/unstaging,
-- and a repo-wide quickfix list of hunks.
--
-- Division of responsibilities in this config:
--   gitsigns  → signs in the sign column, first/last hunk jumps (]H/[H), in-file
--               staging (- and <leader>gh*), persistent inline diff (<leader>gV),
--               and the hunk quickfix list (<leader>ghq / <leader>ghl)
--   keymaps   → next/prev hunk nav (]c/[c) and the = peek key
--   fugitive  → status staging, commit, 3-way merge via :Gdiffsplit!, history
--   util/merge → plugin-free conflict resolution for files with raw markers
--
-- Full code-review workflow cheatsheet: see the header of plugins/fugitive.lua.
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

    -- Hunk preview.
    map("<leader>gD", function()
      require("gitsigns").preview_hunk()
    end, "Preview hunk (float)")
    map("<leader>gd", function()
      require("gitsigns").preview_hunk_inline()
    end, "Preview hunk (inline)")

    -- Persistent whole-file inline diff for the <CR>/O review flow. Toggles the
    -- old/removed lines (show_deleted) + word-level highlighting ON, and they
    -- STAY as you move the cursor and step hunks with ]h — unlike <leader>gd
    -- (preview_hunk_inline), which clears on CursorMoved. show_deleted is the
    -- deprecated-but-functional config behind toggle_deleted(); it only flips the
    -- flag (no redraw), so toggle_word_diff() is paired to force the repaint and
    -- is kept in sync via toggle_deleted's return value. If a future gitsigns
    -- drops show_deleted, only the old-line display stops; word_diff keeps working.
    map("<leader>gV", function()
      local gs = require("gitsigns")
      local on = gs.toggle_deleted()
      gs.toggle_word_diff(on)
    end, "Toggle inline diff (persistent, whole file)")

    -- Staging/unstaging — <leader>gh* namespace.
    --
    -- stage_hunk TOGGLES: calling it on a hunk that is already staged will
    -- unstage it. There is no separate "unstage hunk" binding needed for that.
    map("<leader>ghs", function()
      require("gitsigns").stage_hunk()
    end, "Stage/unstage hunk")
    -- Visual: stage only the selected lines within a hunk.
    map("<leader>ghs", function()
      require("gitsigns").stage_hunk({ vim.fn.line("."), vim.fn.line("v") })
    end, "Stage/unstage hunk (range)", "v")

    -- `-` stages the hunk under the cursor (fires <leader>ghs / stage_hunk) for a
    -- fast ]c → - → ]c → - review loop. It only hijacks `-` when the cursor sits
    -- inside an unstaged hunk; anywhere else it replays the built-in `-` motion
    -- (first non-blank of the previous line), count included. Unstaging stays on
    -- <leader>ghs (toggle) and <leader>ghU — get_hunks only reports unstaged
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

    -- reset_hunk discards the working-tree change (irreversible for unsaved
    -- edits — the hunk is simply dropped, not staged).
    map("<leader>ghr", function()
      require("gitsigns").reset_hunk()
    end, "Reset hunk")
    -- Visual: discard only the selected lines.
    map("<leader>ghr", function()
      require("gitsigns").reset_hunk({ vim.fn.line("."), vim.fn.line("v") })
    end, "Reset hunk (range)", "v")

    -- Whole-buffer operations.
    map("<leader>ghS", function()
      require("gitsigns").stage_buffer()
    end, "Stage buffer")
    map("<leader>ghU", function()
      -- reset_buffer_index unstages all staged hunks in the buffer (index →
      -- HEAD), leaving the working-tree untouched.
      require("gitsigns").reset_buffer_index()
    end, "Unstage buffer (reset index)")
    map("<leader>ghR", function()
      -- DESTRUCTIVE: reset_buffer discards ALL working-tree changes in the
      -- buffer, reverting to the last commit. Cannot be undone.
      require("gitsigns").reset_buffer()
    end, "Reset buffer (discard all — destructive)")

    -- Hunk quickfix lists (native qf, rendered by quicker.nvim).
    --
    -- <leader>ghq is the headline feature: dumps every modified hunk across
    -- every file in the repo into the quickfix list. Navigate with ]q/[q as
    -- usual; `>` in the qf window expands diff context around each entry.
    --
    -- NOTE: the list goes stale as soon as you stage or reset a hunk because
    -- gitsigns recalculates line numbers after each change. Re-run <leader>ghq
    -- to rebuild it after a staging session.
    map("<leader>ghq", function()
      require("gitsigns").setqflist("all", {}, function()
        -- Name the list for the qf header. {what}-only setqflist: the empty
        -- {list} is ignored, only the title property is set, items are preserved.
        vim.fn.setqflist({}, "a", { title = "Gitsigns Hunks" })
      end)
    end, "Hunk qf list (repo-wide)")

    -- Current buffer only — useful for a focused "what did I change here?" scan.
    map("<leader>ghl", function()
      require("gitsigns").setqflist(0, {}, function()
        -- Same title as <leader>ghq for a consistent qf header.
        vim.fn.setqflist({}, "a", { title = "Gitsigns Hunks" })
      end)
    end, "Hunk qf list (buffer)")
  end,
}
