-- Auto-saves a session per (cwd + git branch) to ~/.local/state/nvim/sessions/.
-- Loaded on BufReadPre so its VimLeavePre save hook is registered before exit;
-- does not auto-restore on startup — your snacks dashboard owns startup. Use
-- <leader>qs to restore the session for the current cwd when you want it.
return {
  "folke/persistence.nvim",
  -- Load on VimEnter (every launch, including dashboard) so the keymaps are
  -- always live and the VimLeavePre autosave hook is always registered.
  event = "VimEnter",
  opts = {
    branch = true,
    need = 1,
  },
  keys = {
    { "<leader>qs", function() require("persistence").load() end,                desc = "Restore session (cwd)" },
    { "<leader>ql", function() require("persistence").load({ last = true }) end, desc = "Restore last session" },
    { "<leader>qS", function() require("persistence").select() end,              desc = "Select session" },
    { "<leader>qd", function() require("persistence").stop() end,                desc = "Don't save current session" },
  },
}
