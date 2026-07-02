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
      -- TEST: map the vivendi background layers onto oxocarbon's grays.
      -- on_colors() runs before highlights are built, so these cascade to every
      -- group derived from them. bg_sidebar is set from bg_dim earlier in the
      -- plugin, so it must be overridden explicitly to follow. Defaults (vivendi):
      --   bg_main #000000, bg_alt #0f0f0f, bg_dim #1e1e1e, bg_active #303030.
      -- Remove this block to go back to pure black.
      --
      -- on_colors is shared across BOTH styles, so gate it to vivendi — applying
      -- these dark greys to operandi (light) breaks the light theme on toggle.
      on_colors = function(colors)
        if require("modus-themes.config").options.style ~= "modus_vivendi" then
          return
        end
        colors.bg_main = "#161616" -- oxocarbon base — Normal / editor bg
        colors.bg_alt = "#131313" -- a hair darker than base, keeps subtle depth
        colors.bg_dim = "#262626" -- oxocarbon elevated — floats, popups
        colors.bg_sidebar = "#262626" -- match bg_dim (else stays derived from old bg_dim)
        colors.bg_active = "#393939" -- oxocarbon selection gray
        colors.fg_main = "#d0d0d0" -- oxocarbon base04 — dimmed off-white (was #ffffff)
      end,
      -- Float popups (mini-clue, LSP hover, etc.) render on NormalFloat, which
      -- modus maps to bg_active — my bg_active bump to #393939 made them read
      -- too light. Pin the popup surface to the #262626 elevated grey so the
      -- hierarchy is editor #161616 < popup #262626 < selection #393939.
      -- Gated to vivendi, same as on_colors, so operandi keeps its own float bg.
      on_highlights = function(hl, c)
        if require("modus-themes.config").options.style ~= "modus_vivendi" then
          return
        end
        hl.NormalFloat = { fg = c.fg_main, bg = c.bg_dim } -- fg_main is dimmed #d0d0d0 → popups match
      end,
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
