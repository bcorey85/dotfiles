return {
  src = "rose-pine/neovim",
  name = "rose-pine", -- derive_name would give "neovim"; pin it explicitly
  setup = function()
    require("rose-pine").setup({
      variant = "moon", -- main | moon | dawn
      dark_variant = "moon",
      styles = {
        bold = true,
        italic = true,
        transparency = false,
      },
      palette = {
        -- OneDark background, replacing Moon's purple-tinted surfaces.
        -- base = editor bg; surface/overlay = darker chrome (statusline,
        -- floats, popups) — same trio the old Catppuccin override used.
        moon = {
          base = "#282c34",
          surface = "#21252b",
          overlay = "#1b1f27",
        },
      },
    })
    vim.cmd.colorscheme("rose-pine-moon")
  end,
}
