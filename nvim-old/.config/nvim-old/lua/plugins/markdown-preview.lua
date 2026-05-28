return {
  "iamcco/markdown-preview.nvim",
  cmd = { "MarkdownPreviewToggle", "MarkdownPreview", "MarkdownPreviewStop" },
  ft = { "markdown" },
  init = function()
    vim.g.mkdp_auto_close = 0
  end,
  keys = {
    { "<leader>mm", "<cmd>MarkdownPreview<cr>", desc = "Markdown Preview Start" },
    { "<leader>ms", "<cmd>MarkdownPreviewStop<cr>", desc = "Markdown Preview Stop" },
    { "<leader>mt", "<cmd>MarkdownPreviewToggle<cr>", desc = "Markdown Preview Toggle" },
  },
  build = function()
    vim.fn["mkdp#util#install"]()
  end,
}
