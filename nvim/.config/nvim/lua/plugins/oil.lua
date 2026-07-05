return {
  "stevearc/oil.nvim",
  keys = { { "<leader>e", desc = "Open Oil (parent dir)" } },
  cmd = { "Oil" },
  -- Icon support comes from MiniIcons.mock_nvim_web_devicons(), loaded earlier in plugin_order.
  config = function()
    require("oil").setup({
      watch_for_changes = true,
      view_options = {
        show_hidden = true,
      },
      keymaps = {
        ["<C-l>"] = false,
        ["<C-h>"] = false,
        ["<C-x>"] = { "actions.select", opts = { horizontal = true }, desc = "Open in horizontal split" },
        ["gr"] = { "actions.refresh", mode = "n", desc = "Refresh" },
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
    })

    vim.keymap.set("n", "<leader>e", "<cmd>Oil<cr>", { desc = "Open Oil (parent dir)" })

    -- mini.clue doesn't install its prefix triggers (g, z, etc.) in oil's
    -- buffer-local keymaps, so chords like `gO` fall back to raw timeoutlen
    -- (300ms) — they only fire if you press both keys faster than that.
    -- Re-arm mini.clue's triggers per oil buffer so the `g` prefix waits
    -- indefinitely, like everywhere else.
    vim.api.nvim_create_autocmd("User", {
      pattern = "OilEnter",
      callback = function(args)
        local oil = require("oil")
        if vim.api.nvim_get_current_buf() == args.data.buf and oil.get_cursor_entry() then
          require("mini.clue").ensure_buf_triggers(args.data.buf)
        end
      end,
    })
  end,
}
