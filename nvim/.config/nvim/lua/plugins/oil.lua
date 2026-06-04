return {
  "stevearc/oil.nvim",
  lazy = false,
  dependencies = { "nvim-tree/nvim-web-devicons" },
  opts = {
    watch_for_changes = true,
    view_options = {
      show_hidden = true,
    },
    keymaps = {
      ["q"] = { "actions.close", mode = "n" },
      ["gO"] = {
        mode = "n",
        desc = "Open in file manager",
        callback = function()
          local oil = require("oil")
          local dir = oil.get_current_dir()
          if not dir then
            vim.notify("Oil: not a local directory", vim.log.levels.WARN)
            return
          end
          local entry = oil.get_cursor_entry()
          local target = entry and (dir .. entry.name) or dir
          local is_dir = not entry or entry.type == "directory"

          local cmd
          if vim.fn.has("mac") == 1 then
            cmd = is_dir and { "open", target } or { "open", "-R", target }
          else
            cmd = { "thunar", target }
          end
          vim.fn.jobstart(cmd, { detach = true })
        end,
      },
    },
  },
  keys = {
    { "<leader>e", "<cmd>Oil<cr>", desc = "Open Oil (parent dir)" },
  },
}
