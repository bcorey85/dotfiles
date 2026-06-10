-- gitsigns.nvim — git signs, hunk navigation, in-buffer staging/unstaging,
-- and a repo-wide quickfix list of hunks.
--
-- Division of responsibilities in this config:
--   gitsigns  → signs in the sign column, hunk navigation ([h/]h), staging,
--               and the hunk quickfix list (<leader>ghq / <leader>ghl)
--   fugitive  → status staging, commit, 3-way merge via :Gdiffsplit!, history
--   util/merge → plugin-free conflict resolution for files with raw markers
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

    -- Hunk navigation. {preview=true} opens a small inline float at the
    -- target hunk so you see the diff without a separate step.
    map("]h", function()
      require("gitsigns").nav_hunk("next", { preview = true })
    end, "Next hunk")
    map("[h", function()
      require("gitsigns").nav_hunk("prev", { preview = true })
    end, "Prev hunk")
    map("]H", function()
      require("gitsigns").nav_hunk("last")
    end, "Last hunk")
    map("[H", function()
      require("gitsigns").nav_hunk("first")
    end, "First hunk")

    -- Hunk preview.
    map("<leader>gD", function()
      require("gitsigns").preview_hunk()
    end, "Preview hunk (float)")
    map("<leader>gd", function()
      require("gitsigns").preview_hunk_inline()
    end, "Preview hunk (inline)")

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

    -- `-` stages the hunk under the cursor for a fast ]q → - → ]q → - review
    -- loop. It only hijacks `-` when the cursor sits inside an unstaged hunk;
    -- anywhere else it replays the built-in `-` motion (first non-blank of the
    -- previous line), count included. Unstaging stays on <leader>ghs (toggle)
    -- and <leader>ghU — get_hunks only reports unstaged hunks, so the
    -- fallthrough check can't see staged ones to toggle them back.

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

    -- Hunk quickfix list → Trouble (via the FileType=qf hijack in trouble.lua).
    --
    -- <leader>ghq is the headline feature: dumps every modified hunk across
    -- every file in the repo into the quickfix list, which Trouble then renders
    -- with its preview pane. Navigate with ]q/[q as usual.
    --
    -- NOTE: the list goes stale as soon as you stage or reset a hunk because
    -- gitsigns recalculates line numbers after each change. Re-run <leader>ghq
    -- to rebuild it after a staging session.
    map("<leader>ghq", function()
      require("gitsigns").setqflist("all", {}, function()
        -- Tag this quickfix list so the ]q/[q handlers (trouble.lua) know to
        -- pop gitsigns' inline diff while walking it. {what}-only setqflist:
        -- the empty {list} is ignored, only the title property is set, items
        -- are preserved.
        vim.fn.setqflist({}, "a", { title = "Gitsigns Hunks" })
      end)
    end, "Hunk qf list (repo-wide) → Trouble")

    -- Current buffer only — useful for a focused "what did I change here?" scan.
    map("<leader>ghl", function()
      require("gitsigns").setqflist(0, {}, function()
        -- Same tag as <leader>ghq so ]q/[q show the inline diff regardless of
        -- whether the list was built from the whole repo or a single buffer.
        vim.fn.setqflist({}, "a", { title = "Gitsigns Hunks" })
      end)
    end, "Hunk qf list (buffer) → Trouble")
  end,
}
