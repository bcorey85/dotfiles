return {
  "stevearc/oil.nvim",
  -- Oil should not be lazy-loaded (see oil.nvim docs).
  lazy = false,
  dependencies = { "nvim-tree/nvim-web-devicons" },
  opts = {
    view_options = {
      show_hidden = true,
    },
    -- Merged with oil's defaults (use_default_keymaps stays true).
    keymaps = {
      ["q"] = { "actions.close", mode = "n" },
      -- Always open the entry under the cursor in the system file manager
      -- (Thunar on Linux, Finder on macOS), regardless of xdg-open defaults.
      -- Directory -> open that dir; file -> reveal/select in its folder.
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
