return {
  src = "nyoom-engineering/oxocarbon.nvim",
  name = "oxocarbon", -- derive_name would give "oxocarbon.nvim"; pin it explicitly
  setup = function()
    -- oxocarbon is a plain colorscheme with no setup() — light/dark is selected
    -- by vim.o.background, then `:colorscheme oxocarbon` rebuilds. Apply the
    -- shared light/dark mode (~/.cache/theme-mode) and poll it so a toggle from
    -- tmux (prefix t) or another nvim flips this instance too.
    require("config.theme-sync").start()

    -- markview heading colours (referenced by markview.lua's headings config).
    -- Two muted tones — magenta for H1, blue for H2-H6 — since markview already
    -- gives each level a distinct icon, so the icons carry the hierarchy and the
    -- colour load on prose stays low. MdBullet (list markers) matches the blue.
    --
    -- Neovim clears user highlights on every colorscheme reload, and the
    -- dark↔light toggle is a reload — so re-apply on ColorScheme, and pick
    -- accents by active background so they stay legible on both the dark
    -- (#161616) and light (#ffffff) base. Colours are oxocarbon accents.
    local function set_headings()
      local dark = vim.o.background == "dark"
      local magenta = dark and "#be95ff" or "#673ab7" -- purple (base14 / base12)
      local blue = dark and "#78a9ff" or "#0f62fe" -- blue (base09 / base11)
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
