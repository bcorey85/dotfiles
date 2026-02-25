return {
  "sindrets/diffview.nvim",
  cmd = { "DiffviewOpen", "DiffviewFileHistory" },
  opts = {
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
