return {
  src = "miikanissi/modus-themes.nvim",
  name = "modus-themes",
  setup = function()
    require("modus-themes").setup({
      style = "auto",
      variants = {
        modus_operandi = "default",
        modus_vivendi = "default",
      },
      dim_inactive = false,
      styles = {
        comments = { italic = true },
        keywords = { italic = true },
        functions = {},
        variables = {},
      },
    })

    -- Override modus-vivendi bg/fg with oxocarbon colors — must be registered
    -- before theme-sync.start() so it fires on the initial colorscheme load too.
    vim.api.nvim_create_autocmd("ColorScheme", {
      group = vim.api.nvim_create_augroup("OxocarbonOverride", { clear = true }),
      callback = function()
        if vim.o.background == "dark" then
          vim.api.nvim_set_hl(0, "Normal", { bg = "#161616", fg = "#f2f4f8" })
          vim.api.nvim_set_hl(0, "NormalNC", { bg = "#161616", fg = "#f2f4f8" })
          vim.api.nvim_set_hl(0, "NormalFloat", { bg = "#161616", fg = "#f2f4f8" })
        end
      end,
    })

    -- Sync background from ~/.cache/theme-mode and poll for changes.
    require("config.theme-sync").start()

    -- markview heading colours (referenced by markview.lua's headings config).
    local function set_headings()
      local dark = vim.o.background == "dark"
      local magenta = dark and "#feacd0" or "#721045"
      local blue = dark and "#79a8ff" or "#3548cf"
      local hl = vim.api.nvim_set_hl
      hl(0, "MdHeading1", { fg = magenta, bold = true })
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
