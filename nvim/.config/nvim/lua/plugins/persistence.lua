-- persistence.nvim — session save/restore: the "always there" / emacs-daemon
-- half of the workflow. setup() auto-registers a VimLeavePre autosave (per cwd
-- AND per git branch — `branch=true` default), and the VimEnter hook below
-- auto-restores the cwd session when nvim is launched with no file args. So
-- `tmux-sessionizer` dropping you into a project (or just `nvim` in a repo)
-- reopens buffers/splits/cursor exactly where you left off.
--
-- <leader>q is the "+quit/session" namespace (mini.clue) — mirrors Doom `SPC q`.
-- qq (quit all) lives in config/keymaps.lua.

-- Throwaway nvims must never save OR restore a session, or they'd clobber the
-- real project session / dump a full layout into a popup:
--   • tmux popups: prefix g (neogit), prefix s (git hunk qf), prefix d
--     (codediff review), prefix C-c/C-a (org capture/agenda) — argc 0, so the
--     no-args autoload would fire. Same env flags the smart-splits spec
--     guards on.
--   • headless nvim (CI / scripted checks): no UI ⇒ list_uis() is empty.
-- (need=1 already blocks autosave for the buffer-less neogit popup, but the
-- git-qf popup can open real files — so we also hard-stop saving below.)
local disabled = vim.env.NEOGIT_POPUP ~= nil
  or vim.env.GIT_QF_POPUP ~= nil
  or vim.env.CODEDIFF_POPUP ~= nil
  or vim.env.ORG_POPUP ~= nil
  or #vim.api.nvim_list_uis() == 0

return {
  "folke/persistence.nvim",
  lazy = false,
  config = function()
    local persistence = require("persistence")
    persistence.setup() -- defaults: dir under stdpath('state'), per-cwd + per-branch, need=1

    -- Neovim's DEFAULT sessionoptions is "blank,buffers,curdir,folds,help,
    -- tabpages,winsize,terminal" — `blank` and `terminal` make mksession capture
    -- empty scratch buffers and terminal buffers, both of which restore as junk.
    -- Drop them (and `help`); keep only what's useful to reopen a project layout.
    vim.o.sessionoptions = "buffers,curdir,folds,tabpages,winsize"

    if disabled then
      persistence.stop() -- throwaway / headless: undo the autosave start() wired in setup()
      return
    end

    -- Auto-restore the cwd session when nvim opens with no file arguments (the
    -- sessionizer / bare-`nvim` flow). With args you asked for a specific file —
    -- don't override that. nested=true so restored buffers fire FileType/BufRead
    -- (LSP attach, treesitter, etc.). load() is no-op-safe when no session exists.
    vim.api.nvim_create_autocmd("VimEnter", {
      group = vim.api.nvim_create_augroup("PersistenceAutoload", { clear = true }),
      nested = true,
      callback = function()
        if vim.fn.argc(-1) == 0 then
          persistence.load()
        end
      end,
    })

    -- Before each save, wipe special / non-file buffers so mksession never
    -- badd's them into the session (they restore as garbage): terminals,
    -- quickfix, help, oil:// dir listings, NeogitStatus, [No Name] scratch,
    -- and stray fs junk like .DS_Store. `need`'s own filter only decides IF we
    -- save, not WHICH buffers land in the session — this controls the latter.
    -- Runs on VimLeavePre (via SavePre), so wiping the current buffer is safe.
    vim.api.nvim_create_autocmd("User", {
      pattern = "PersistenceSavePre",
      group = vim.api.nvim_create_augroup("PersistenceCleanBufs", { clear = true }),
      callback = function()
        for _, b in ipairs(vim.api.nvim_list_bufs()) do
          if vim.api.nvim_buf_is_valid(b) then
            local name = vim.api.nvim_buf_get_name(b)
            local special = vim.bo[b].buftype ~= "" -- terminal/nofile/acwrite/help/qf/prompt
              or vim.bo[b].filetype == "oil"
              or vim.bo[b].filetype:match("^Neogit") ~= nil
              or name == "" -- [No Name] / blank
              or name:match("^%w+://") ~= nil -- oil://, fugitive://, etc.
              or name:match("%.DS_Store$") ~= nil
            if special then
              -- Must delete, not just unlist: `buffers` in sessionoptions makes
              -- mksession save HIDDEN buffers too, so an unlisted-but-alive buffer
              -- still lands in the session. force handles modified/terminal bufs.
              pcall(vim.api.nvim_buf_delete, b, { force = true })
            end
          end
        end
      end,
    })

    -- <leader>q namespace (mirrors Doom `SPC q`).
    local map = function(lhs, fn, desc)
      vim.keymap.set("n", lhs, fn, { desc = desc })
    end
    map("<leader>ql", function()
      persistence.load({ last = true })
    end, "Session: restore last")
    map("<leader>qL", function()
      persistence.load()
    end, "Session: restore (this dir)")
    map("<leader>qs", function()
      persistence.save()
    end, "Session: save now")
    map("<leader>qS", function()
      persistence.select()
    end, "Session: select")
    map("<leader>qd", function()
      persistence.stop()
    end, "Session: stop saving (this session)")
  end,
}
