-- mini.indentscope — animated indent guide for the scope under the cursor.
-- The MiniIndentscopeSymbol highlight is already defined in theme.lua
-- (custom_highlights), so it goes live automatically here with no theme.lua edit.
-- Animation is disabled — instant draw keeps the display snappy without the
-- stepping motion that feels distracting on fast cursor movement.
return {
  src = "echasnovski/mini.nvim",
  setup = function()
    local indentscope = require("mini.indentscope")

    indentscope.setup({
      symbol = "│",
      draw = {
        -- gen_animation.none() returns an animation fn that always yields 0ms
        -- wait, making the indicator appear instantly on cursor move.
        animation = indentscope.gen_animation.none(),
      },
      options = {
        try_as_border = true,
      },
    })

    -- Suppress the indicator in utility buffers where an indent scope line
    -- is visual noise or outright wrong (e.g. help, quickfix, oil dir listing).
    vim.api.nvim_create_autocmd("FileType", {
      group = vim.api.nvim_create_augroup("MiniIndentscopeDisable", { clear = true }),
      pattern = {
        "checkhealth",
        "NeogitStatus",
        "git",
        "help",
        "lspinfo",
        "mason",
        "oil",
        "qf",
        "undotree",
      },
      callback = function()
        vim.b.miniindentscope_disable = true
      end,
    })
  end,
}
