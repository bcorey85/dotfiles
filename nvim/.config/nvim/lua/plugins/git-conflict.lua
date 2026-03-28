return {
  "spacedentist/resolve.nvim",
  event = { "BufReadPre", "BufNewFile" },
  opts = {
    default_keymaps = false,
  },
  keys = {
    { "co", "<cmd>ResolveOurs<cr>", desc = "Choose Ours" },
    { "ct", "<cmd>ResolveTheirs<cr>", desc = "Choose Theirs" },
    { "cb", "<cmd>ResolveBoth<cr>", desc = "Choose Both" },
    { "c0", "<cmd>ResolveNone<cr>", desc = "Choose None" },
    { "]x", "<cmd>ResolveNext<cr>", desc = "Next Conflict" },
    { "[x", "<cmd>ResolvePrev<cr>", desc = "Previous Conflict" },
  },
}
