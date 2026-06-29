-- neogit — Magit-style git client (status buffer + transient popups).
--
-- Replaces vim-fugitive. Gitsigns stays for in-file signs/hunk nav (see
-- plugins/gitsigns.lua and plugins/diffs.lua for the division of labor).
--
-- The magit-shaped workflow: one entry key (<leader>gg), then transient
-- popups inside the status buffer — c commit, P push, p pull, f fetch, l log,
-- r rebase, b branch, etc. The old fugitive keymaps (<leader>gc/gp/gP/gF/gf/
-- gb/gw/gW/gl/gL/gu) are dropped on purpose: neogit's popups replace them.
-- Plugin-independent keepers (<leader>gr gh PR, <leader>gt push+upstream)
-- live below, converted off fugitive's :Git to vim.system.
--
-- Filetype of the status buffer is `NeogitStatus` (used by mini-indentscope,
-- diffs.nvim, and the jump-to-existing scan below).
--
-- Neogit emits User autocmds (NeogitCommitComplete, NeogitPushComplete, etc.)
-- which statusline.lua subscribes to in place of fugitive's FugitiveChanged.
return {
  src = "NeogitOrg/neogit",
  setup = function()
    -- ]f / [f — jump to next / previous FILE in the status list (magit ]]/[[ feel).
    -- neogit's built-ins don't cover this: }/{ walk hunk headers (and dive INTO a
    -- collapsed file), <c-n>/<c-p> walk only the top-level sections (Unstaged /
    -- Staged / Stashes / …) — neither steps file-to-file across sections. File rows
    -- render as `Item`-tagged components (neogit/buffers/status/ui.lua), so we
    -- collect each Item's header line and jump to the nearest one in `dir`.
    -- (Bare ]/[ were avoided: under neogit's `nowait` user-mapping bind they'd
    --  shadow the default ]c/[c diff-scroll. ]f/[f sits beside that family.)
    local function goto_file(dir)
      local ok, status_buf = pcall(require, "neogit.buffers.status")
      if not ok then
        return
      end
      local status = status_buf.instance()
      if not (status and status.buffer) then
        return
      end
      local ui = status.buffer.ui
      local cur = vim.api.nvim_win_get_cursor(0)[1]
      local is_file = function(node)
        return node.options.tag == "Item"
      end
      -- header line = first buffer line each Item is detected on (lines ascend, so
      -- the first sighting of an Item id is its header, above its expanded hunks).
      local rows, seen = {}, {}
      for line = 1, vim.api.nvim_buf_line_count(0) do
        local c = ui:get_component_on_line(line, is_file)
        if c and not seen[c.position.row_start] then
          seen[c.position.row_start] = true
          rows[#rows + 1] = line
        end
      end
      local target
      if dir > 0 then
        for _, r in ipairs(rows) do
          if r > cur then
            target = r
            break
          end
        end
      else
        for i = #rows, 1, -1 do
          if rows[i] < cur then
            target = rows[i]
            break
          end
        end
      end
      if target then
        vim.api.nvim_win_set_cursor(0, { target, 0 })
      end
    end

    require("neogit").setup({
      -- magit ]]/[[ file navigation — neogit lacks a file-level action, so these
      -- are custom (see goto_file above). Function-valued status mappings are
      -- bound buffer-local by neogit (lib/buffer.lua :: user_mappings).
      mappings = {
        status = {
          ["]f"] = function()
            goto_file(1)
          end,
          ["[f"] = function()
            goto_file(-1)
          end,
        },
      },
      -- `tab` is true to fugitive's old `tab Git` behavior: <leader>gg opens a
      -- throwaway tab, q closes it and returns to where you were.
      kind = "tab",
      -- Disable neogit's own signs (gitsigns owns the sign column in file
      -- buffers; neogit's signs would clash).
      disable_signs = true,
      -- Treesitter-powered diff highlighting in the status buffer. diffs.nvim
      -- keeps its fugitive/diff-mode integration for standalone diff buffers.
      treesitter_diff_highlight = true,
      word_diff_highlight = true,
      -- Per-project settings persist to ~/.local/share/nvim/neogit/ — keep
      -- them so a tweaked status view survives, but ignore anything that'd
      -- fight this config.
      remember_settings = true,
      use_per_project_settings = true,
      ignored_settings = {},
      -- Filewatcher auto-refreshes the status buffer when the repo changes on
      -- disk (e.g. a commit lands from another tmux pane). Neogit uses a real
      -- inotify/FSEvents watcher (not a poll), so there is no interval to set —
      -- only the `enabled` flag matters.
      filewatcher = { enabled = true },
      graph_style = "ascii",
      commit_order = "topo",
      disable_insert_on_commit = "auto",
      highlight = { italic = true, bold = true, underline = true },
      -- Floats already get a rounded border from vim.o.winborder (options.lua).
      floating = { relative = "editor", width = 0.8, height = 0.7, style = "minimal", border = "rounded" },
      disable_line_numbers = true,
      disable_relative_line_numbers = true,
      integrations = {
        -- All integrations default to `nil`, which means auto-detect via
        -- `pcall(require, ...)`. snacks is installed (plugins/snacks.lua) →
        -- auto-detected for menu selection (multi-select over vim.ui.select).
        -- Uninstalled pickers (telescope/fzf-lua/mini.pick) fail the pcall
        -- silently. diffview IS installed now (plugins/diffview.lua) — enable it
        -- explicitly so neogit hands diff/conflict views off to the 3-way tool.
        diffview = true,
      },
    })

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    -- <leader>gg — open the neogit status buffer, or JUMP back to an already-
    -- open one (in any tab/window). Idempotent: from an O-opened review tab it
    -- snaps you straight back to status — no :tabclose — and never piles up
    -- duplicate status tabs. Mirrors the old fugitive idempotent-open shape.
    map("<leader>gg", function()
      for _, tab in ipairs(vim.api.nvim_list_tabpages()) do
        for _, win in ipairs(vim.api.nvim_tabpage_list_wins(tab)) do
          if vim.bo[vim.api.nvim_win_get_buf(win)].filetype == "NeogitStatus" then
            vim.api.nvim_set_current_tabpage(tab)
            vim.api.nvim_set_current_win(win)
            return
          end
        end
      end
      vim.cmd("Neogit")
    end, "Neogit status (jump to existing or open)")

    -- In the tmux `prefix g` popup, `q` in the status buffer quits the
    -- throwaway nvim so the popup dismisses like lazygit. Outside the popup
    -- the env var is unset, so neogit's own `q` (Close) keeps its normal
    -- meaning (close the status tab and return to the prior one).
    --
    -- vim.schedule is essential: neogit sets filetype=NeogitStatus and THEN,
    -- still inside its open() path, binds its own buffer-local `q` → Close.
    -- A bare FileType autocmd fires between those two steps, so neogit's q
    -- would overwrite ours. Scheduling defers our set to the next event-loop
    -- tick, after neogit's setup completes — ours wins.
    vim.api.nvim_create_autocmd("FileType", {
      group = vim.api.nvim_create_augroup("neogit-popup-quit", { clear = true }),
      pattern = "NeogitStatus",
      callback = function(ev)
        if vim.env.NEOGIT_POPUP ~= nil then
          vim.schedule(function()
            vim.keymap.set("n", "q", "<cmd>qa<cr>", {
              buffer = ev.buf,
              desc = "Close neogit popup",
            })
          end)
        end
      end,
    })

    -- <leader>gb — fuzzy branch checkout (mirrors Doom/magit `SPC g b`,
    -- magit-branch-checkout). Snacks' git_branches picker checks out the
    -- selected branch on <CR>; branch create/rename/delete stay in neogit's
    -- B BranchPopup (<leader>gg then B).
    map("<leader>gb", function()
      Snacks.picker.git_branches()
    end, "Checkout branch")

    -- <leader>gL — log of commits touching the current file (mirrors Doom
    -- `SPC g L`, magit-log-buffer-file). Repo-wide log stays inside neogit
    -- (<leader>gg then l l). <CR> on a commit shows its diff. Guarded: without
    -- a real file git_log_file runs `git log -- ` with an empty pathspec.
    map("<leader>gL", function()
      if vim.fn.expand("%") == "" or vim.bo.buftype ~= "" then
        vim.notify("No file in buffer for git log", vim.log.levels.WARN)
        return
      end
      Snacks.picker.git_log_file()
    end, "Log (current file)")

    -- Neogit buffers are special (non-listed, buftype=acwrite/nofile) and bind
    -- their keys buffer-local with `nowait=true` (lib/buffer.lua). Two knock-on
    -- effects, both fixed here on the Neogit* FileType:
    --
    --   1. wrap — global `wrap` is off (options.lua), so diffs in the status and
    --      commit views overflow off-screen. Force it back on per-window.
    --   2. <leader> maps — mini.clue only auto-installs its <Leader> trigger in
    --      listed buffers, so it never lands in Neogit's. Without the trigger,
    --      <space> is swallowed and the next keys hit Neogit's nowait maps
    --      directly (u→Unstage, w→WorktreePopup), eating e.g. <leader>uw.
    --      MiniClue.ensure_buf_triggers() re-installs the trigger buffer-local
    --      (mini.clue docs :: "Triggers in special buffers"). vim.schedule defers
    --      it past Neogit's own mapping setup so the trigger wins precedence.
    vim.api.nvim_create_autocmd("FileType", {
      group = vim.api.nvim_create_augroup("neogit-wrap-and-clue", { clear = true }),
      pattern = "Neogit*",
      callback = function(ev)
        vim.wo.wrap = true
        vim.wo.linebreak = false
        vim.wo.breakindent = true
        vim.schedule(function()
          local ok, miniclue = pcall(require, "mini.clue")
          if ok and vim.api.nvim_buf_is_valid(ev.buf) then
            miniclue.ensure_buf_triggers(ev.buf)
          end
        end)
      end,
    })

    -- <leader>gr — open the current branch's PR on GitHub, or start one if
    -- none exists. Pure vim.system / gh call — independent of any git plugin.
    map("<leader>gr", function()
      vim.system({ "gh", "pr", "view", "--web" }, { text = true }, function(out)
        if out.code ~= 0 then
          vim.system({ "gh", "pr", "create", "--web" })
        end
      end)
    end, "Open/create PR on GitHub")

    -- <leader>gt — push current branch and set its upstream tracking branch.
    -- Prompts for the remote branch name (defaults to the current local
    -- branch). Uses vim.system so this file has zero dependency on fugitive.
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
        vim.system({ "git", "push", "-u", "origin", input }, { text = true }, function(out)
          if out.code ~= 0 then
            vim.schedule(function()
              vim.notify("git push failed: " .. (out.stderr or ""), vim.log.levels.ERROR)
            end)
          end
        end)
      end)
    end, "Git push + set upstream tracking (prompt)")
  end,
}

