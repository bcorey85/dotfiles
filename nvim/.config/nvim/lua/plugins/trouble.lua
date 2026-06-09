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
      -- Quickfix/loclist default to grouping by filename, which renders a file
      -- header AND an item row beneath it — for one-item-per-file lists (e.g. a
      -- Telescope file list sent with <C-q>) that reads as duplicates. Flatten
      -- to one row per entry. The matched line text for grep results shows in
      -- the preview pane; add `{text:ts}` back to `format` to inline it.
      modes = {
        qflist = {
          groups = {},
          format = "{file_icon} {filename} {pos}",
        },
        loclist = {
          groups = {},
          format = "{file_icon} {filename} {pos}",
        },
      },
    })

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>lt", "<cmd>Trouble diagnostics toggle<cr>", "Diagnostics (workspace)")
    map("<leader>lT", "<cmd>Trouble diagnostics toggle filter.buf=0<cr>", "Diagnostics (buffer)")
    map("<leader>ls", "<cmd>Trouble symbols toggle focus=false<cr>", "Symbols (sidebar)")
    map("<leader>lS", "<cmd>Trouble lsp toggle focus=false win.position=right<cr>", "LSP defs/refs/impls")
    map("<leader>lq", "<cmd>Trouble qflist toggle<cr>", "Quickfix list")
    map("<leader>ll", "<cmd>Trouble loclist toggle<cr>", "Location list")

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

    -- Make Trouble the default surface for the native quickfix and location
    -- lists. Any `qf` window — `:copen`/`:lopen`, `:make`, `:grep`, Telescope's
    -- <C-q>, `vim.lsp.buf.references`, etc. — is closed and reopened in Trouble.
    -- The underlying list is untouched, so `:cnext`/`:cdo`/`]q` still work; only
    -- the window is swapped. Folke flags this as unofficial (brief flicker on
    -- open), but it's the only hook that catches every path that opens a list.
    vim.api.nvim_create_autocmd("FileType", {
      group = vim.api.nvim_create_augroup("trouble-qf-hijack", { clear = true }),
      pattern = "qf",
      callback = function(ev)
        vim.schedule(function()
          local win = vim.fn.bufwinid(ev.buf)
          if win == -1 then
            return
          end
          -- loclist windows report loclist==1 in getwininfo; route accordingly.
          local info = vim.fn.getwininfo(win)[1]
          local mode = (info and info.loclist == 1) and "loclist" or "qflist"
          vim.api.nvim_win_close(win, true)
          require("trouble").open(mode)
        end)
      end,
    })
  end,
}
