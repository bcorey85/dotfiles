-- nvim-treesitter-context — sticky header showing the enclosing scope
-- (function, class, if-block, etc.) when it scrolls off screen.
-- Placed after "treesitter" in plugin_order so its queries resolve correctly.
return {
  src = "nvim-treesitter/nvim-treesitter-context",
  setup = function()
    require("treesitter-context").setup({
      max_lines = 4,
    })

    -- <leader>uc: toggle the context header on/off, consistent with the
    -- other <leader>u* UI-toggle keymaps in keymaps.lua.
    vim.keymap.set("n", "<leader>uc", function()
      require("treesitter-context").toggle()
    end, { desc = "Toggle context header" })

    -- [x: jump the cursor up to the context line shown in the sticky header.
    -- Takes a count for nested contexts (2[x → outer scope). [c is the README's
    -- suggestion but it's taken by diff/hunk navigation in this config.
    vim.keymap.set("n", "[x", function()
      require("treesitter-context").go_to_context(vim.v.count1)
    end, { desc = "Jump to context start" })
  end,
}
