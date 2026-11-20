-- monoglow (wnkz/monoglow.nvim) — theme-mode family "monoglow": void dark,
-- light light. Eager, so it is on the rtp before theme-sync.start(). The teal
-- and the diff washes are repeated by hand in theme-mode and its ports.
return {
  "wnkz/monoglow.nvim",
  lazy = false,
  priority = 1000,
  opts = {
    -- Teal glow: stock #1bfd9c at hue 170. on_colors runs after the derived
    -- tables are built, so they are set too.
    on_colors = function(colors)
      local teal = colors.is_light and colors.blue2 or "#33e6c6"
      colors.glow = teal
      colors.mode.insert.bg = teal
      colors.mode.command.bg = teal
      colors.terminal.green = teal
      colors.terminal.green_bright = teal
    end,
    -- Stock diff rows are solid blocks with ground-coloured text.
    on_highlights = function(highlights, colors)
      local blend = require("monoglow.util").blend
      highlights.DiffAdd = { bg = blend(colors.git.add, 0.15, colors.bg) }
      highlights.DiffDelete = { bg = blend(colors.git.delete, 0.15, colors.bg) }
      highlights.DiffChange = { bg = blend(colors.gray6, 0.15, colors.bg) }
      highlights.Boolean = highlights["@constant.builtin"]
      highlights.DiffText ={ bg = blend(colors.gray6, 0.35, colors.bg) }
    end,
  },
}
