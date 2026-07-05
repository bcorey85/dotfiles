-- quicker.nvim — editable quickfix/loclist with context expansion.
-- Replaces trouble.nvim: native qf/loclist windows, no extra UI layer.
-- cfilter (`:Cfilter`/`:Lfilter`) ships with Neovim and is loaded here
-- since this is the natural home for quickfix tooling.
return {
  "stevearc/quicker.nvim",
  ft = "qf",
  keys = {
    { "<leader>ld", desc = "Diagnostics → quickfix (workspace)" },
    { "<leader>lD", desc = "Diagnostics → loclist (buffer)" },
    { "<leader>lq", desc = "Quickfix (toggle)" },
    { "<leader>lL", desc = "Loclist (toggle)" },
  },
  config = function()
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
        -- Buffer-local filtering, usable while focused IN the qf/loclist window
        -- (leader maps are awkward here). cmdline-prefill via feedkeys (not <Cmd>)
        -- so the cursor lands ready for a BARE pattern. No `/` prefix: cfilter
        -- reads `/pat` as the literal pattern unless you close it (`/pat/`), so a
        -- lone slash silently matches nothing — the undelimited `:Cfilter pat`
        -- form is what works. f keeps matches, F rejects them — the narrow step of
        -- the search-and-replace pipeline (Snacks.picker.grep → <C-q> → f/F → :cdo s///).
        {
          "f",
          function()
            vim.api.nvim_feedkeys(":Cfilter ", "n", false)
          end,
          desc = "Filter quickfix (keep)",
        },
        {
          "F",
          function()
            vim.api.nvim_feedkeys(":Cfilter! ", "n", false)
          end,
          desc = "Filter quickfix (reject)",
        },
      },
    })

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>ld", function()
      vim.diagnostic.setqflist({ open = true })
    end, "Diagnostics → quickfix (workspace)")
    map("<leader>lD", function()
      vim.diagnostic.setloclist({ open = true })
    end, "Diagnostics → loclist (buffer)")
    map("<leader>lq", function()
      require("quicker").toggle()
    end, "Quickfix (toggle)")
    map("<leader>lL", function()
      require("quicker").toggle({ loclist = true })
    end, "Loclist (toggle)")

    -- Plain qf navigation. Centers on hop (zz) to match the rest of the config's
    -- center-on-jump behavior (]c/[c, n/N, <C-d>/<C-u>, gitsigns hunk nav). No
    -- diff-on-hop: when walking the <leader>cq hunk list, use = (whole-file inline
    -- overlay) or <leader>gd (:Gitsigns diffthis, real navigable split) to see a
    -- hunk's change. The notify replaces the bare "E553: No more items".
    map("[q", function()
      if pcall(vim.cmd.cprev) then
        vim.cmd("normal! zz")
      else
        vim.notify("No previous quickfix item", vim.log.levels.WARN)
      end
    end, "Previous quickfix item")
    map("]q", function()
      if pcall(vim.cmd.cnext) then
        vim.cmd("normal! zz")
      else
        vim.notify("No next quickfix item", vim.log.levels.WARN)
      end
    end, "Next quickfix item")
  end,
}
