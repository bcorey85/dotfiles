return {
  "folke/trouble.nvim",
  cmd = "Trouble",
  opts = {
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
  },
  keys = {
    { "<leader>xt", "<cmd>Trouble diagnostics toggle<cr>",                       desc = "Diagnostics (workspace)" },
    { "<leader>xT", "<cmd>Trouble diagnostics toggle filter.buf=0<cr>",          desc = "Diagnostics (buffer)" },
    { "<leader>xs", "<cmd>Trouble symbols toggle focus=false<cr>",               desc = "Symbols (sidebar)" },
    { "<leader>xS", "<cmd>Trouble lsp toggle focus=false win.position=right<cr>", desc = "LSP defs/refs/impls" },
    { "<leader>xQ", "<cmd>Trouble qflist toggle<cr>",                            desc = "Quickfix (trouble)" },
    { "<leader>xL", "<cmd>Trouble loclist toggle<cr>",                           desc = "Location list (trouble)" },
    -- Navigate inside trouble lists from anywhere. These wrap the existing
    -- ]q/[q so they jump in trouble when it's the active list, else quickfix.
    {
      "[q",
      function()
        if require("trouble").is_open() then
          require("trouble").prev({ skip_groups = true, jump = true })
        else
          local ok = pcall(vim.cmd.cprev)
          if not ok then vim.notify("No previous quickfix item", vim.log.levels.WARN) end
        end
      end,
      desc = "Previous trouble/quickfix",
    },
    {
      "]q",
      function()
        if require("trouble").is_open() then
          require("trouble").next({ skip_groups = true, jump = true })
        else
          local ok = pcall(vim.cmd.cnext)
          if not ok then vim.notify("No next quickfix item", vim.log.levels.WARN) end
        end
      end,
      desc = "Next trouble/quickfix",
    },
  },
}
