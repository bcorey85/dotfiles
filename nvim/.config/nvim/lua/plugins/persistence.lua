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
--   • tmux popups: prefix g (neogit), prefix s (git hunk qf) — argc 0, so the
--     no-args autoload would fire. Same env flags the smart-splits spec guards on.
--   • headless nvim (CI / scripted checks): no UI ⇒ list_uis() is empty.
-- (need=1 already blocks autosave for the buffer-less neogit popup, but the
-- git-qf popup can open real files — so we also hard-stop saving below.)
local disabled = vim.env.NEOGIT_POPUP ~= nil
  or vim.env.GIT_QF_POPUP ~= nil
  or #vim.api.nvim_list_uis() == 0

return {
  src = "folke/persistence.nvim",
  setup = function()
    local persistence = require("persistence")
    persistence.setup() -- defaults: dir under stdpath('state'), per-cwd + per-branch, need=1

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
