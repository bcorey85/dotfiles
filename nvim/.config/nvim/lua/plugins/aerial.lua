-- aerial.nvim — code outline / symbol tree as a sidebar buffer.
-- Same author as oil/conform/quicker, so it slots into the buffer-native
-- workflow. Backends fall back treesitter → lsp → markdown, so it works in
-- plain markdown buffers too (no LSP required). Placed after treesitter and
-- lspconfig in plugin_order since both back the symbol queries.
return {
  src = "stevearc/aerial.nvim",
  setup = function()
    require("aerial").setup({
      backends = { "treesitter", "lsp", "markdown", "man" },
      layout = { default_direction = "left", min_width = 30 },
      -- Collect symbols on attach instead of waiting for the panel to open.
      -- With the default (lazy_load = true) the {x/}x symbol-hop maps silently
      -- no-op until you've opened the outline at least once for the buffer.
      lazy_load = false,
      -- Follow the cursor: highlight the symbol under the cursor and keep it
      -- in view, matching the sticky-context behavior from treesitter-context.
      highlight_on_hover = true,
      show_guides = true,
      -- `{` / `}` jump prev/next symbol inside the aerial window (defaults).
    })

    -- <leader>uo: toggle the outline, consistent with the other <leader>u*
    -- UI-toggle keymaps (uc context, us spelling, ud diagnostics).
    vim.keymap.set("n", "<leader>uo", "<cmd>AerialToggle!<cr>", { desc = "Toggle outline" })

    -- {x / }x: jump up/down the symbol tree from anywhere in the file, with a
    -- count for nested scopes. Mirrors [x (context jump) from treesitter-context.
    vim.keymap.set("n", "{x", function()
      require("aerial").prev(vim.v.count1)
      vim.cmd("normal! zz")
    end, { desc = "Prev symbol" })
    vim.keymap.set("n", "}x", function()
      require("aerial").next(vim.v.count1)
      vim.cmd("normal! zz")
    end, { desc = "Next symbol" })
  end,
}
