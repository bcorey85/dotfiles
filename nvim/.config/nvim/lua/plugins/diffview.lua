return {
  "sindrets/diffview.nvim",
  cmd = { "DiffviewOpen", "DiffviewFileHistory" },
  opts = {
    keymaps = {
      file_panel = {
        { "n", "<C-d>", function()
          local key = vim.api.nvim_replace_termcodes("<C-d>", true, false, true)
          for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
            if vim.wo[win].diff then
              vim.api.nvim_win_call(win, function() vim.cmd("normal! " .. key) end)
              return
            end
          end
        end, { desc = "Scroll diff down" } },
        { "n", "<C-u>", function()
          local key = vim.api.nvim_replace_termcodes("<C-u>", true, false, true)
          for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
            if vim.wo[win].diff then
              vim.api.nvim_win_call(win, function() vim.cmd("normal! " .. key) end)
              return
            end
          end
        end, { desc = "Scroll diff up" } },
      },
    },
    view = {
      merge_tool = {
        layout = "diff1_plain",
        disable_diagnostics = true,
      },
    },
    hooks = {
      diff_buf_read = function()
        vim.opt_local.foldenable = false
      end,
    },
  },
  keys = {
    {
      "<leader>dd",
      function()
        local lib = require("diffview.lib")
        if lib.get_current_view() then
          vim.cmd("DiffviewClose")
          local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
          if zoomed == "1" then
            vim.fn.system("tmux resize-pane -Z")
          end
        else
          vim.fn.system("tmux resize-pane -Z")
          vim.cmd("DiffviewOpen")
        end
      end,
      desc = "Toggle Diff View",
    },
    {
      "<leader>dm",
      "<cmd>DiffviewOpen<cr>",
      desc = "Merge Conflicts",
    },
    {
      "<leader>df",
      function()
        local lib = require("diffview.lib")
        if lib.get_current_view() then
          vim.cmd("DiffviewClose")
          local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
          if zoomed == "1" then
            vim.fn.system("tmux resize-pane -Z")
          end
        else
          vim.fn.system("tmux resize-pane -Z")
          vim.cmd("DiffviewFileHistory %")
        end
      end,
      desc = "Toggle File History",
    },
  },
}
