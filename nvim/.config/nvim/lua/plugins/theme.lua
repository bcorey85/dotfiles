return {
  {
    "sainnhe/sonokai",
    lazy = false,
    priority = 1000,
    config = function()
      vim.g.sonokai_style = "shusia"
      vim.g.sonokai_colors_override = {
        bg0 = { "#212121", "234" },
        bg1 = { "#292929", "235" },
        bg2 = { "#313131", "236" },
        bg3 = { "#393939", "237" },
        bg4 = { "#414141", "238" },
        fg = { "#e0ddd6", "250" },
        green = { "#4a9880", "66" },
        orange = { "#D78787", "174" },
        yellow = { "#b5a6c8", "146" },
        blue = { "#7ec8b0", "73" },
        grey = { "#605858", "240" }, -- warmer comment color
        red = { "#d4727a", "168" }, -- softer red, less alarm-y
      }
      vim.cmd.colorscheme("sonokai")

      -- cursor line highlight
      vim.api.nvim_set_hl(0, "CursorLine", { bg = "#2a2525" })
      vim.api.nvim_set_hl(0, "CursorLineNr", { fg = "#e0ddd6", bold = true })

      -- brighter line numbers
      vim.api.nvim_set_hl(0, "LineNr", { fg = "#605858" })

      -- warm up comments to dusty mauve
      vim.api.nvim_set_hl(0, "Comment", { fg = "#7a6b78", italic = true })

      -- soften diagnostic signs
      vim.api.nvim_set_hl(0, "DiagnosticSignError", { fg = "#d4727a" })
      vim.api.nvim_set_hl(0, "DiagnosticError", { fg = "#d4727a" })
    end,
  },
}
