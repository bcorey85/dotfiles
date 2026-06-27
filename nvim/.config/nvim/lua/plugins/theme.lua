return {
  src = "rose-pine/neovim",
  name = "rose-pine", -- derive_name would give "neovim"; pin it explicitly
  setup = function()
    require("rose-pine").setup({
      variant = "moon",
      dark_variant = "moon",
      styles = { bold = true, italic = true, transparency = false },
      palette = {
        -- OneDark faded-black background, replacing Moon's purple-tinted
        -- surfaces. base = editor bg; surface/overlay = darker chrome.
        moon = { base = "#282c34", surface = "#21252b", overlay = "#1b1f27" },
      },
      highlight_groups = {
        -- markview heading colours (referenced by markview.lua's headings
        -- config). Calmed from the old 6-colour rainbow to two muted tones —
        -- rose for H1, foam for H2-H6 — since markview already gives each level
        -- a distinct icon, so the icons carry the hierarchy and the colour load
        -- on prose stays low. MdBullet (list markers) matches the foam chrome.
        MdHeading1 = { fg = "rose", bold = true },
        MdHeading2 = { fg = "foam", bold = true },
        MdHeading3 = { fg = "foam", bold = true },
        MdHeading4 = { fg = "foam", bold = true },
        MdHeading5 = { fg = "foam", bold = true },
        MdHeading6 = { fg = "foam", bold = true },
        MdBullet = { fg = "foam" },
      },
    })
    vim.cmd.colorscheme("rose-pine-moon")
  end,
}
