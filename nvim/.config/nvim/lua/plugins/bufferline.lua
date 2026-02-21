return {
  {
    "akinsho/bufferline.nvim",
    opts = {
      options = {
        always_show_bufferline = true,
        -- Prevent bufferline from forcing showtabline on every render
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
      -- Show bufferline only when at least one real file buffer exists
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
  },
}
