return {
  {
    "akinsho/bufferline.nvim",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = {
        always_show_bufferline = true,
        auto_toggle_bufferline = false,
        numbers = "ordinal",
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
      { "<leader>bl", "<cmd>BufferLineCloseRight<cr>", desc = "Delete buffers to the right" },
      { "<leader>bh", "<cmd>BufferLineCloseLeft<cr>", desc = "Delete buffers to the left" },
      { "<leader>bd", function() require("mini.bufremove").delete() end, desc = "Delete buffer" },
      { "<leader>bD", "<cmd>:bd<cr>", desc = "Delete buffer + window" },
      { "<leader>bo", function() local cur = vim.api.nvim_get_current_buf(); for _, b in ipairs(vim.api.nvim_list_bufs()) do if b ~= cur and vim.bo[b].buflisted then require("mini.bufremove").delete(b) end end end, desc = "Delete other buffers" },
      { "<leader>bb", "<cmd>e #<cr>", desc = "Switch to other buffer" },
      { "<S-h>", "<cmd>BufferLineCyclePrev<cr>", desc = "Prev buffer" },
      { "<S-l>", "<cmd>BufferLineCycleNext<cr>", desc = "Next buffer" },
      { "[b", "<cmd>BufferLineCyclePrev<cr>", desc = "Prev buffer" },
      { "]b", "<cmd>BufferLineCycleNext<cr>", desc = "Next buffer" },
      { "<leader>1", "<cmd>BufferLineGoToBuffer 1<cr>", desc = "which_key_ignore" },
      { "<leader>2", "<cmd>BufferLineGoToBuffer 2<cr>", desc = "which_key_ignore" },
      { "<leader>3", "<cmd>BufferLineGoToBuffer 3<cr>", desc = "which_key_ignore" },
      { "<leader>4", "<cmd>BufferLineGoToBuffer 4<cr>", desc = "which_key_ignore" },
      { "<leader>5", "<cmd>BufferLineGoToBuffer 5<cr>", desc = "which_key_ignore" },
      { "<leader>6", "<cmd>BufferLineGoToBuffer 6<cr>", desc = "which_key_ignore" },
      { "<leader>7", "<cmd>BufferLineGoToBuffer 7<cr>", desc = "which_key_ignore" },
      { "<leader>8", "<cmd>BufferLineGoToBuffer 8<cr>", desc = "which_key_ignore" },
      { "<leader>9", "<cmd>BufferLineGoToBuffer 9<cr>", desc = "which_key_ignore" },
    },
  },
}
