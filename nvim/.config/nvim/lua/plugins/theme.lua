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

    -- markview heading colours — kanagawa palette
    -- Magenta for H1, blue for H2-H6. MdBullet matches the blue.
    local hl = vim.api.nvim_set_hl
    hl(0, "MdHeading1", { fg = "#D2A6FF", bold = true })  -- autumnMagenta
    hl(0, "MdHeading2", { fg = "#7E9CD8", bold = true })  -- dragonBlue
    hl(0, "MdHeading3", { fg = "#7E9CD8", bold = true })  -- dragonBlue
    hl(0, "MdHeading4", { fg = "#7E9CD8", bold = true })  -- dragonBlue
    hl(0, "MdHeading5", { fg = "#7E9CD8", bold = true })  -- dragonBlue
    hl(0, "MdHeading6", { fg = "#7E9CD8", bold = true })  -- dragonBlue
    hl(0, "MdBullet", { fg = "#7E9CD8" })                 -- dragonBlue
  end,
}
