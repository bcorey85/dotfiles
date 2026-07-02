return {
  src = "miikanissi/modus-themes.nvim",
  name = "modus-themes", -- derive_name would give "modus-themes.nvim"; pin it explicitly
  setup = function()
    require("modus-themes").setup({
      style = "modus_vivendi", -- default colorscheme when none is set explicitly below
      variants = { -- per-style: default | tinted | deuteranopia | tritanopia
        modus_vivendi = "default",
        modus_operandi = "default",
      },
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
    --
    -- Neovim clears user highlights on every colorscheme reload, and the
    -- vivendi↔operandi toggle (<leader>ut) is a reload — so re-apply on
    -- ColorScheme, and pick accents by active style so they stay legible on both
    -- the dark (vivendi) and light (operandi) base. Colours are modus accents.
    -- NB: modus-themes doesn't flip vim.o.background or colors_name between
    -- styles (both stay "dark"/"modus") — the active style lives in its config.
    local function set_headings()
      local ok, cfg = pcall(require, "modus-themes.config")
      local dark = not (ok and cfg.options.style == "modus_operandi")
      local magenta = dark and "#b6a0ff" or "#531ab6" -- magenta-cooler
      local blue = dark and "#79a8ff" or "#0031a9" -- blue / blue-intense
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
