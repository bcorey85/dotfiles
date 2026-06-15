-- vim-fugitive — interactive Git status buffer and full `:Git` command suite,
-- running alongside gitsigns (in-file hunk signs/staging/nav). Fugitive owns the
-- status buffer, commits, diff splits, and history; gitsigns owns the in-file
-- review experience. Keys are split across three files — this header is the one
-- place that documents the whole review workflow.
--
-- ════════════════════════════════════════════════════════════════════════════
-- CODE REVIEW WORKFLOW
-- ════════════════════════════════════════════════════════════════════════════
--
-- The loop:  <leader>gg → <CR> → read the file → ]c/= peek → - stage → <leader>gg
--
--   <leader>gg   open the status buffer, or JUMP back to it if already open
--                (idempotent — no duplicate status tabs). [this file]
--   <CR>         on a file in status: open it WHOLE in a new tab — read in
--                context, not as diff noise. The reflex review gear. [this file]
--   <leader>gV   toggle a PERSISTENT whole-file inline diff (old lines +
--                word-diff) that survives cursor movement. [gitsigns.lua]
--   ]c / [c      next/prev hunk + center; native diff-change motion inside a
--                real diff (dv). Quiet — no auto-preview. [keymaps.lua]
--   =            on a hunk: one-key inline preview (transient); off a hunk:
--                native `=` reindent operator. [keymaps.lua]
--   -            on a hunk: stage it (stage_hunk); off a hunk: native `-`
--                motion. Fast ]c → - → ]c → - staging loop. [gitsigns.lua]
--   <leader>gw   :Gwrite — stage the whole current file from any buffer.
--   <leader>gW   :Git reset -- % — unstage the whole current file. [this file]
--   ]H / [H      jump to first/last hunk in the buffer. [gitsigns.lua]
--
-- Diff-scan gear (when you already know the file): in status, `dv`/`dd`/`dh`/`ds`
-- open diff splits and the status window auto-shrinks to 30% [this file]; `=`
-- expands fugitive's own inline diff; `o`/`gO`/`O` open split/vsplit/tab.
--
-- In-file staging detail (gitsigns.lua): <leader>cs stage/unstage hunk (toggle,
-- n+v), <leader>cr reset hunk, <leader>cS/cU stage/unstage buffer, <leader>cR
-- discard buffer (destructive), <leader>cq/cl hunk quickfix repo/buffer,
-- <leader>gd/gD inline/float one-off hunk preview.
--
-- Git commands (this file): <leader>gc commit · gp/gP pull/push · gF push-force ·
-- gf fetch · gb blame · gl/gL/gu log repo/file/unpushed · gt push+upstream ·
-- gr open/create PR. History is :Git log (newest-first pager buffer).
--
-- Note: `-` and `=` only STAGE/peek unstaged hunks (get_hunks reports unstaged
-- only); unstage via <leader>cs / <leader>cU / <leader>gW.
-- ════════════════════════════════════════════════════════════════════════════
--
return {
  src = "tpope/vim-fugitive",
  setup = function()
    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    -- Jump to an already-open fugitive status buffer (in any tab/window) if one
    -- exists, else open one in a new tab. Idempotent: pressing it from an
    -- O-opened review tab snaps you straict back to status — no :tabclose — and
    -- it never piles up duplicate status tabs the way a bare `tab Git` does.
    map("<leader>gg", function()
      for _, tab in ipairs(vim.api.nvim_list_tabpages()) do
        for _, win in ipairs(vim.api.nvim_tabpage_list_wins(tab)) do
          if vim.bo[vim.api.nvim_win_get_buf(win)].filetype == "fugitive" then
            vim.api.nvim_set_current_tabpage(tab)
            vim.api.nvim_set_current_win(win)
            -- The status buffer is a cached snapshot. gitsigns stages by writing
            -- the index directly (- / _ / <leader>c*), so fugitive never learns
            -- the index moved and the file still shows "unstaged" until the
            -- buffer is rebuilt. DidChange expires + reloads the status buffers,
            -- so landing here always reflects current staging — no close/reopen.
            pcall(vim.fn["fugitive#DidChange"])
            return
          end
        end
      end
      vim.cmd("tab Git")
    end, "Git status (jump to existing or open)")
    map("<leader>gc", "<cmd>Git commit<cr>", "Git commit")
    map("<leader>gp", "<cmd>Git pull<cr>", "Git pull")
    map("<leader>gP", "<cmd>Git push<cr>", "Git push")
    map("<leader>gF", "<cmd>Git push --force-with-lease<cr>", "Git push --force-with-lease")
    map("<leader>gf", "<cmd>Git fetch<cr>", "Git fetch")
    map("<leader>gb", "<cmd>Git blame<cr>", "Git blame (fugitive)")

    -- Stage the current file from wherever you're reading it (working buffer,
    -- O-tab, or the dv diff's rict pane) — no trip back to the status buffer.
    map("<leader>gw", "<cmd>Gwrite<cr>", "Git write (stage current file)")
    map("<leader>gW", "<cmd>Git reset -- %<cr>", "Git unstage current file")

    -- Git log via fugitive's native pager buffer (filetype=git): newest commit
    -- on top, <CR> opens the commit under the cursor. Deliberately NOT :Gclog —
    -- that routes through the quickfix, which for fugitive commits uses the sha
    -- path as the filename and sorts accordingly, landing on the lowest SHA (a
    -- stale commit) instead of HEAD. The pager buffer bypasses the quickfix
    -- entirely, so order is honest and navigation is via the buffer itself.
    map("<leader>gl", "<cmd>Git log --oneline<cr>", "Git log (repo)")
    map("<leader>gL", "<cmd>Git log --oneline -- %<cr>", "Git log (current file)")
    map("<leader>gu", "<cmd>Git log --oneline @{upstream}..HEAD<cr>", "Git log unpushed")

    -- Push current branch and set its upstream tracking branch. Prompts for
    -- the remote branch name (defaults to the current local branch).
    map("<leader>gt", function()
      local branch = require("util.git").branch()
      if not branch then
        vim.notify("Not on a branch", vim.log.levels.WARN)
        return
      end
      vim.ui.input({ prompt = "Remote tracking branch: ", default = branch }, function(input)
        if not input or input == "" then
          return
        end
        vim.cmd("Git push -u origin " .. input)
      end)
    end, "Git push + set upstream tracking (prompt)")

    -- Open the current branch's PR on GitHub, or start one if none exists.
    -- Pure vim.system / gh call — independent of any git plugin.
    map("<leader>gr", function()
      vim.system({ "gh", "pr", "view", "--web" }, { text = true }, function(out)
        if out.code ~= 0 then
          vim.system({ "gh", "pr", "create", "--web" })
        end
      end)
    end, "Open/create PR on GitHub")

    -- In fugitive's status buffer, make <CR> open the file under the cursor in a
    -- new tab (fugitive's `O`) — the whole file in context, not a diff split.
    -- Read it top-to-bottom, then step through its changes with gitsigns ]h/[h;
    -- <leader>gg jumps back to this status buffer. The reflex key defaults to the
    -- gear that rebuilds the mental map; the diff-scan gears stay on their native
    -- keys: `dv` (vsplit diff), `o` (split), `gO` (vsplit), `=` (inline diff).
    vim.api.nvim_create_autocmd("FileType", {
      group = vim.api.nvim_create_augroup("fugitive-cr-tab", { clear = true }),
      pattern = "fugitive",
      callback = function(ev)
        vim.keymap.set("n", "<CR>", function()
          vim.cmd.normal({ "O", bang = false })
        end, {
          buffer = ev.buf,
          desc = "Fugitive: open file in new tab (whole-file review)",
        })
        -- In the tmux popup (prefix g), `q` quits the throwaway nvim so the
        -- popup dismisses like lazygit. Outside the popup the env var is unset,
        -- so `q` keeps its normal meaning and fugitive's `gq` still closes the
        -- status buffer.
        if vim.env.FUGITIVE_POPUP ~= nil then
          vim.keymap.set("n", "q", "<cmd>qa<cr>", {
            buffer = ev.buf,
            desc = "Close fugitive popup",
          })
        end
      end,
    })

    -- Diff-split layout: whenever a fugitive diff buffer opens (dv/dd/dh/ds all
    -- create a `fugitive://` object buffer), shrink the status window on top to
    -- ~30% so the diff panes below get the room. Reacting to the diff buffer
    -- instead of wrapping the `dv` key avoids recursion (fugitive's `dv` calls a
    -- script-local function) and covers every diff-split key, not just `dv`.
    vim.api.nvim_create_autocmd("BufWinEnter", {
      group = vim.api.nvim_create_augroup("fugitive-diff-resize", { clear = true }),
      pattern = "fugitive://*",
      callback = function()
        for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
          if vim.bo[vim.api.nvim_win_get_buf(win)].filetype == "fugitive" then
            vim.api.nvim_win_set_height(win, math.floor(vim.o.lines * 0.3))
            break
          end
        end
      end,
    })
  end,
}
