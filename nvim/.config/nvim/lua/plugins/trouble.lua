return {
  src = "folke/trouble.nvim",
  setup = function()
    require("trouble").setup({
      -- Focus the list on open, auto-close when its source is empty (no more
      -- diagnostics). Default buffer keys:
      --   q close · ? help · r refresh · dd delete · P preview
      --   zo/zc fold · zM/zR fold all
      --
      -- Default `<cr>` is context-sensitive: jump on items, fold-toggle on group
      -- headers. We override it to always jump — use zo/zc for folds.
      focus = true,
      auto_close = true,
      keys = {
        ["<cr>"] = "jump",
        ["o"] = "jump",
      },
    })

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>xt", "<cmd>Trouble diagnostics toggle<cr>", "Diagnostics (workspace)")
    map("<leader>xT", "<cmd>Trouble diagnostics toggle filter.buf=0<cr>", "Diagnostics (buffer)")
    map("<leader>xs", "<cmd>Trouble symbols toggle focus=false<cr>", "Symbols (sidebar)")
    map("<leader>xS", "<cmd>Trouble lsp toggle focus=false win.position=right<cr>", "LSP defs/refs/impls")
    map("<leader>xQ", "<cmd>Trouble qflist toggle<cr>", "Quickfix (trouble)")
    map("<leader>xL", "<cmd>Trouble loclist toggle<cr>", "Location list (trouble)")

    -- Navigate inside trouble lists from anywhere. These wrap the existing
    -- ]q/[q so they jump in trouble when it's the active list, else quickfix.
    map("[q", function()
      if require("trouble").is_open() then
        require("trouble").prev({ skip_groups = true, jump = true })
      else
        local ok = pcall(vim.cmd.cprev)
        if not ok then
          vim.notify("No previous quickfix item", vim.log.levels.WARN)
        end
      end
    end, "Previous trouble/quickfix")
    map("]q", function()
      if require("trouble").is_open() then
        require("trouble").next({ skip_groups = true, jump = true })
      else
        local ok = pcall(vim.cmd.cnext)
        if not ok then
          vim.notify("No next quickfix item", vim.log.levels.WARN)
        end
      end
    end, "Next trouble/quickfix")
  end,
}
