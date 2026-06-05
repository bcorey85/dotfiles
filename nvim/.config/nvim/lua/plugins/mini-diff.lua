return {
  {
    "echasnovski/mini.diff",
    event = { "BufReadPre", "BufNewFile" },
    config = function()
      local diff = require("mini.diff")
      diff.setup({
        view = {
          style = "sign",
          signs = { add = "▎", change = "▎", delete = "▎" },
        },
        source = diff.gen_source.git(),
        mappings = {
          apply = "",
          reset = "",
          textobject = "",
          goto_prev = "[h",
          goto_next = "]h",
          goto_first = "[H",
          goto_last = "]H",
        },
      })

      vim.keymap.set("n", "<leader>gd", function()
        diff.toggle_overlay()
      end, { desc = "Toggle diff overlay" })
    end,
  },
}
