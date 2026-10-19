-- barbar.nvim — the listed buffers as tabs along the top. Loads with the first
-- file, so the dashboard has no tabline; auto_hide = 0 hides it again once the
-- last buffer closes. Unnamed buffers get no tab. Also loads with fyler, so the
-- tabline stops short of its sidebar. Icons come from the mini.icons devicons mock.
-- buffer_manager reads and writes this tab order.
return {
  "romgrk/barbar.nvim",
  event = { "BufReadPre", "BufNewFile" },
  ft = "fyler_finder",
  init = function()
    vim.g.barbar_auto_setup = false
  end,
  opts = {
    animation = false,
    auto_hide = 0,
    exclude_name = { "" },
    sidebar_filetypes = { fyler_finder = true },
  },
  keys = {
    { "[b", "<cmd>BufferPrevious<cr>", desc = "Prev buffer" },
    { "]b", "<cmd>BufferNext<cr>", desc = "Next buffer" },
    { "<leader>bh", "<cmd>BufferMovePrevious<cr>", desc = "Move buffer left" },
    { "<leader>bl", "<cmd>BufferMoveNext<cr>", desc = "Move buffer right" },
    { "<leader>bj", "<cmd>BufferPick<cr>", desc = "Jump to buffer" },
    { "<leader>bp", "<cmd>BufferPin<cr>", desc = "Toggle pin" },
    { "<leader>1", "<cmd>BufferGoto 1<cr>", desc = "Buffer 1" },
    { "<leader>2", "<cmd>BufferGoto 2<cr>", desc = "Buffer 2" },
    { "<leader>3", "<cmd>BufferGoto 3<cr>", desc = "Buffer 3" },
    { "<leader>4", "<cmd>BufferGoto 4<cr>", desc = "Buffer 4" },
  },
}
