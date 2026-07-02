return {
  src = "miikanissi/modus-themes.nvim",
  name = "modus-themes",
  setup = function()
    require("modus-themes").setup({
      style = "modus_vivendi",
      transparent = false,
      dim_inactive = false,
      styles = {
        comments = { italic = true },
        keywords = { italic = true },
      },
    })

    vim.cmd.colorscheme("modus_vivendi")

    -- markview heading colours (referenced by markview.lua's headings config).
    -- Two muted tones — magenta for H1, blue for H2-H6 — since markview already
    -- gives each level a distinct icon, so the icons carry the hierarchy and the
    -- colour load on prose stays low. MdBullet (list markers) matches the blue.
    local hl = vim.api.nvim_set_hl
    hl(0, "MdHeading1", { fg = "#c678dd", bold = true })
    hl(0, "MdHeading2", { fg = "#51afef", bold = true })
    hl(0, "MdHeading3", { fg = "#51afef", bold = true })
    hl(0, "MdHeading4", { fg = "#51afef", bold = true })
    hl(0, "MdHeading5", { fg = "#51afef", bold = true })
    hl(0, "MdHeading6", { fg = "#51afef", bold = true })
    hl(0, "MdBullet", { fg = "#51afef" })
  end,
}
