return {
  "spacedentist/resolve.nvim",
  event = { "BufReadPre", "BufNewFile" },
  opts = {
    default_keymaps = true,
    on_conflict_detected = function(args)
      local opts = { buffer = args.bufnr, silent = true, remap = true }
      vim.keymap.set("n", "co", "<Plug>(resolve-ours)", vim.tbl_extend("force", opts, { desc = "Choose ours" }))
      vim.keymap.set("n", "ct", "<Plug>(resolve-theirs)", vim.tbl_extend("force", opts, { desc = "Choose theirs" }))
      vim.keymap.set("n", "cb", "<Plug>(resolve-both)", vim.tbl_extend("force", opts, { desc = "Choose both" }))
      vim.keymap.set("n", "c0", "<Plug>(resolve-none)", vim.tbl_extend("force", opts, { desc = "Choose none" }))
    end,
  },
}
