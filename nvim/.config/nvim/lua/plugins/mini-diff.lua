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
          -- goto_* handled by the guarded keymaps below: mini.diff's built-ins
          -- raise "Buffer N is not enabled" when pressed in a buffer it isn't
          -- tracking (dashboard, help, terminals, ...).
          goto_prev = "",
          goto_next = "",
          goto_first = "",
          goto_last = "",
        },
      })

      vim.keymap.set("n", "<leader>gd", function()
        diff.toggle_overlay()
      end, { desc = "Toggle diff overlay" })

      -- Only jump when the current buffer actually has mini.diff data, so [h/]h
      -- in a non-diff buffer no-op instead of erroring.
      local function goto_hunk(direction)
        return function()
          if diff.get_buf_data(0) then
            diff.goto_hunk(direction)
          end
        end
      end
      vim.keymap.set("n", "[h", goto_hunk("prev"), { desc = "Prev hunk" })
      vim.keymap.set("n", "]h", goto_hunk("next"), { desc = "Next hunk" })
      vim.keymap.set("n", "[H", goto_hunk("first"), { desc = "First hunk" })
      vim.keymap.set("n", "]H", goto_hunk("last"), { desc = "Last hunk" })
    end,
  },
}
