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
        green = { "#7ec8b0", "108" },
        orange = { "#D78787", "174" },
        yellow = { "#b5a6c8", "146" },
      }
      vim.cmd.colorscheme("sonokai")
    end,
  },
}
