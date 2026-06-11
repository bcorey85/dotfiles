-- persistence.nvim — automatic session save/restore per working directory.
-- Sessions are written to stdpath("state")/sessions/ on VimLeavePre and
-- restored on demand; nothing runs automatically on startup (explicit load
-- keeps behavior predictable when opening a single file).
return {
  src = "folke/persistence.nvim",
  setup = function()
    require("persistence").setup({})

    -- <leader>qs: restore the session for the current working directory.
    vim.keymap.set("n", "<leader>qs", function()
      require("persistence").load()
    end, { desc = "Restore session (cwd)" })

    -- <leader>ql: restore the most-recently saved session regardless of cwd.
    vim.keymap.set("n", "<leader>ql", function()
      require("persistence").load({ last = true })
    end, { desc = "Restore last session" })

    -- <leader>qS: interactive picker (vim.ui.select) over all saved sessions.
    vim.keymap.set("n", "<leader>qS", function()
      require("persistence").select()
    end, { desc = "Select session" })

    -- <leader>qd: stop persistence so the current session is NOT written on
    -- exit — useful when you want to close without clobbering a saved state.
    vim.keymap.set("n", "<leader>qd", function()
      require("persistence").stop()
    end, { desc = "Stop session saving" })
  end,
}
