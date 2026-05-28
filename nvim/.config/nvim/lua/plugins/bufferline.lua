return {
  {
    "akinsho/bufferline.nvim",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = {
        always_show_bufferline = true,
        auto_toggle_bufferline = false,
      },
      highlights = {
        fill = { bg = "#21282c" },
        background = { bg = "#21282c" },
        buffer_selected = { bg = "#273136" },
      },
    },
    config = function(_, opts)
      require("bufferline").setup(opts)
      local function update_tabline()
        for _, buf in ipairs(vim.api.nvim_list_bufs()) do
          if vim.bo[buf].buflisted and vim.api.nvim_buf_get_name(buf) ~= "" then
            vim.o.showtabline = 2
            return
          end
        end
        vim.o.showtabline = 0
      end
      vim.api.nvim_create_autocmd({ "BufAdd", "BufEnter", "BufDelete", "BufWipeout" }, {
        callback = vim.schedule_wrap(update_tabline),
      })
      update_tabline()
    end,
    keys = {
      { "<leader>bp", "<cmd>BufferLineTogglePin<cr>", desc = "Toggle pin" },
      { "<leader>bP", "<cmd>BufferLineGroupClose ungrouped<cr>", desc = "Delete non-pinned buffers" },
      { "<S-h>", "<cmd>BufferLineCyclePrev<cr>", desc = "Prev buffer" },
      { "<S-l>", "<cmd>BufferLineCycleNext<cr>", desc = "Next buffer" },
    },
  },
}
