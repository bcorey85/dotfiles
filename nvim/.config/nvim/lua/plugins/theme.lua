return {
  src = "EdenEast/nightfox.nvim",
  name = "nightfox",
  setup = function()
    require("nightfox").setup({
      options = { styles = { comments = "italic", keywords = "italic" } },
    })

    -- Sync background from ~/.cache/theme-mode and poll for changes.
    require("config.theme-sync").start()

    -- markview heading colours (referenced by markview.lua's headings config).
    local function set_headings()
      local dark = vim.o.background == "dark"
      local purple = dark and "#9d79d6" or "#6e33ce"
      local blue = dark and "#719cd6" or "#2848a9"
      local hl = vim.api.nvim_set_hl
      hl(0, "MdHeading1", { fg = purple, bold = true })
      hl(0, "MdHeading2", { fg = blue, bold = true })
      hl(0, "MdHeading3", { fg = blue, bold = true })
      hl(0, "MdHeading4", { fg = blue, bold = true })
      hl(0, "MdHeading5", { fg = blue, bold = true })
      hl(0, "MdHeading6", { fg = blue, bold = true })
      hl(0, "MdBullet", { fg = blue })
    end
    set_headings()
    vim.api.nvim_create_autocmd("ColorScheme", {
      group = vim.api.nvim_create_augroup("MarkviewHeadings", { clear = true }),
      callback = set_headings,
    })
  end,
}
