-- vim-fugitive — interactive Git status buffer and full `:Git` command suite.
--
-- Fugitive owns the `:Git` command and provides an interactive status buffer
-- where `-` stages/unstages files, `=` expands an inline diff, and `<cr>`
-- opens a vertical diff (remapped from the default file-open; `o`/`gO`/`O`
-- still open in split/vsplit/tab). It runs alongside gitsigns (in-file hunk
-- signs/navigation). History is via :Git log (newest-first pager buffer).
--
return {
  src = "tpope/vim-fugitive",
  setup = function()
    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>gg", "<cmd>tab Git<cr>", "Git status (fugitive panel)")
    map("<leader>gc", "<cmd>Git commit<cr>", "Git commit")
    map("<leader>gp", "<cmd>Git pull<cr>", "Git pull")
    map("<leader>gP", "<cmd>Git push<cr>", "Git push")
    map("<leader>gF", "<cmd>Git push --force-with-lease<cr>", "Git push --force-with-lease")
    map("<leader>gf", "<cmd>Git fetch<cr>", "Git fetch")
    map("<leader>gb", "<cmd>Git blame<cr>", "Git blame (fugitive)")

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

    -- In fugitive's status buffer, make <CR> open a vertical diff (fugitive's
    -- `dv`) on the file under the cursor instead of editing it, then resize the
    -- status window (top) to ~30% of screen height so the diff panes below get
    -- ~60%. The left/right width of the two diff windows is left as-is.
    -- The default file-open is still on `o` (split) / `gO` (vsplit) / `O` (tab).
    vim.api.nvim_create_autocmd("FileType", {
      group = vim.api.nvim_create_augroup("fugitive-cr-diff", { clear = true }),
      pattern = "fugitive",
      callback = function(ev)
        vim.keymap.set("n", "<CR>", function()
          vim.cmd.normal({ "dv", bang = false })
          for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
            if vim.bo[vim.api.nvim_win_get_buf(win)].filetype == "fugitive" then
              vim.api.nvim_win_set_height(win, math.floor(vim.o.lines * 0.3))
              break
            end
          end
        end, {
          buffer = ev.buf,
          desc = "Fugitive: vertical diff (dv), status 30% height",
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
  end,
}
