return {
  "iamcco/markdown-preview.nvim",
  cmd = { "MarkdownPreviewToggle", "MarkdownPreview", "MarkdownPreviewStop" },
  ft = { "markdown" },
  keys = {
    { "<leader>mm", "<cmd>MarkdownPreview<cr>", desc = "Markdown Preview Start" },
    { "<leader>ms", "<cmd>MarkdownPreviewStop<cr>", desc = "Markdown Preview Stop" },
    { "<leader>mt", "<cmd>MarkdownPreviewToggle<cr>", desc = "Markdown Preview Toggle" },
  },
  build = function()
    vim.fn["mkdp#util#install"]()
  end,
}
