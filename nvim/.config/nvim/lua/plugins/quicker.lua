-- quicker.nvim — editable quickfix/loclist with context expansion.
-- Replaces trouble.nvim: native qf/loclist windows, no extra UI layer.
-- cfilter (`:Cfilter`/`:Lfilter`) ships with Neovim and is loaded here
-- since this is the natural home for quickfix tooling.
return {
  src = "stevearc/quicker.nvim",
  setup = function()
    -- cfilter ships with Neovim; enables :Cfilter/:Lfilter to narrow qf/loclist by pattern.
    vim.cmd.packadd("cfilter")

    require("quicker").setup({
      keys = {
        {
          ">",
          function()
            require("quicker").expand({ before = 2, after = 2, add_to_existing = true })
          end,
          desc = "Expand quickfix context",
        },
        {
          "<",
          function()
            require("quicker").collapse()
          end,
          desc = "Collapse quickfix context",
        },
      },
    })

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>lt", function()
      vim.diagnostic.setqflist({ open = true })
    end, "Diagnostics → quickfix (workspace)")
    map("<leader>lT", function()
      vim.diagnostic.setloclist({ open = true })
    end, "Diagnostics → loclist (buffer)")
    map("<leader>lq", function()
      require("quicker").toggle()
    end, "Quickfix (toggle)")
    map("<leader>ll", function()
      require("quicker").toggle({ loclist = true })
    end, "Loclist (toggle)")

    map("[q", function()
      local ok = pcall(vim.cmd.cprev)
      if not ok then
        vim.notify("No previous quickfix item", vim.log.levels.WARN)
      end
    end, "Previous quickfix item")
    map("]q", function()
      local ok = pcall(vim.cmd.cnext)
      if not ok then
        vim.notify("No next quickfix item", vim.log.levels.WARN)
      end
    end, "Next quickfix item")
  end,
}
