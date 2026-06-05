return {
  {
    "gbprod/yanky.nvim",
    event = { "BufReadPost", "BufNewFile" },
    dependencies = {
      { "kkharji/sqlite.lua" },
    },
    opts = {
      ring = {
        history_length = 100,
        storage = "sqlite",
        sync_with_numbered_registers = true,
        cancel_event = "update",
      },
      picker = {
        select = {
          action = nil,
        },
        telescope = {
          use_default_mappings = true,
        },
      },
      system_clipboard = {
        sync_with_ring = true,
      },
      highlight = {
        on_put = true,
        on_yank = true,
        timer = 500,
      },
      preserve_cursor_position = {
        enabled = true,
      },
    },
    keys = {
      { "p", "<Plug>(YankyPutAfter)", mode = { "n", "x" }, desc = "Put after" },
      { "P", "<Plug>(YankyPutBefore)", mode = { "n", "x" }, desc = "Put before" },
      { "gp", "<Plug>(YankyGPutAfter)", mode = { "n", "x" }, desc = "Put after (stay)" },
      { "gP", "<Plug>(YankyGPutBefore)", mode = { "n", "x" }, desc = "Put before (stay)" },
      { "<C-p>", "<Plug>(YankyPreviousEntry)", desc = "Yanky: prev entry" },
      { "<C-n>", "<Plug>(YankyNextEntry)", desc = "Yanky: next entry" },
    },
  },
}
