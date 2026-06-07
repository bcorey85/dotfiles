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
        -- User override (toggled by <leader>ub). When hidden, never auto-show.
        if vim.g.bufferline_hidden then
          vim.o.showtabline = 0
          return
        end
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
      -- Trial: start with the tabline hidden. Toggle with <leader>ub.
      if vim.g.bufferline_hidden == nil then
        vim.g.bufferline_hidden = true
      end
      update_tabline()
    end,
    keys = {
      { "<leader>bp", "<cmd>BufferLineTogglePin<cr>", desc = "Toggle pin" },
      { "<leader>bP", "<cmd>BufferLineGroupClose ungrouped<cr>", desc = "Delete non-pinned buffers" },
      { "<leader>bl", "<cmd>BufferLineCloseRight<cr>", desc = "Delete buffers to the right" },
      { "<leader>bh", "<cmd>BufferLineCloseLeft<cr>", desc = "Delete buffers to the left" },
      {
        "<leader>bd",
        function()
          require("mini.bufremove").delete()
        end,
        desc = "Delete buffer",
      },
      {
        "<leader>bD",
        function()
          require("mini.bufremove").delete(0, true)
        end,
        desc = "Delete buffer (force)",
      },
      {
        "<leader>bo",
        function()
          local cur = vim.api.nvim_get_current_buf()
          for _, b in ipairs(vim.api.nvim_list_bufs()) do
            if b ~= cur and vim.bo[b].buflisted then
              require("mini.bufremove").delete(b)
            end
          end
        end,
        desc = "Delete other buffers",
      },
      { "<leader>bb", "<cmd>e #<cr>", desc = "Switch to other buffer" },
      { "<S-h>", "<cmd>BufferLineCyclePrev<cr>", desc = "Prev buffer" },
      { "<S-l>", "<cmd>BufferLineCycleNext<cr>", desc = "Next buffer" },
      { "[b", "<cmd>BufferLineCyclePrev<cr>", desc = "Prev buffer" },
      { "]b", "<cmd>BufferLineCycleNext<cr>", desc = "Next buffer" },
      {
        "<leader>ub",
        function()
          vim.g.bufferline_hidden = not vim.g.bufferline_hidden
          vim.o.showtabline = vim.g.bufferline_hidden and 0 or 2
        end,
        desc = "Toggle bufferline",
      },
    },
  },
}
