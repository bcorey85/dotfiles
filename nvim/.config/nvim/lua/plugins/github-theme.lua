-- github-theme — the active colorscheme: github_dark_dimmed (dark) /
-- github_light (light), synced via lua/config/theme-sync.lua off
-- ~/.cache/theme-mode. Stock palette, no overrides.
return {
  "projekt0n/github-nvim-theme",
  name = "github-theme",
  lazy = false,
  priority = 1000,
  config = function()
    -- Sync background from ~/.cache/theme-mode and poll for changes.
    require("config.theme-sync").start()

    -- markview heading colours (referenced by markview.lua's headings config).
    -- github accents: purple/blue (dark: #b083f0/#539bf5, light: #8250df/#0969da).
    local function set_headings()
      local dark = vim.o.background == "dark"
      local purple = dark and "#b083f0" or "#8250df"
      local blue = dark and "#539bf5" or "#0969da"
      local hl = vim.api.nvim_set_hl
      hl(0, "MdHeading1", { fg = purple, bold = true })
      hl(0, "MdHeading2", { fg = blue, bold = true })
      hl(0, "MdHeading3", { fg = blue, bold = true })
      hl(0, "MdHeading4", { fg = blue, bold = true })
      hl(0, "MdHeading5", { fg = blue, bold = true })
      hl(0, "MdHeading6", { fg = blue, bold = true })
      hl(0, "MdBullet", { fg = blue })
    end

    -- gitsigns word-diff readability (the `=` whole-file inline overlay, keymaps.lua).
    -- gitsigns' inline word-diff groups (GitSigns{Change,Add,Delete}LnInline)
    -- default to `reverse = true`, which paints dim token fgs (comments worst)
    -- as unreadable blocks. Replace reverse with the theme's own diff
    -- backgrounds + a forced bright Normal fg, so the emphasised word reads on
    -- ANY underlying token. Values are read from the resolved palette at
    -- ColorScheme time, so this is theme-agnostic and tracks the light↔dark toggle.
    local function set_word_diff()
      local hl = vim.api.nvim_set_hl
      local function bg_of(name)
        return vim.api.nvim_get_hl(0, { name = name, link = false }).bg
      end
      local fg = vim.api.nvim_get_hl(0, { name = "Normal", link = false }).fg
      -- DiffText (word-emphasis) sits a shade lighter than DiffChange (the
      -- line bg), so the changed word still pops out of its own changed line.
      hl(0, "GitSignsChangeLnInline", { fg = fg, bg = bg_of("DiffText"), bold = true })
      hl(0, "GitSignsAddLnInline", { fg = fg, bg = bg_of("DiffAdd"), bold = true })
      hl(0, "GitSignsDeleteLnInline", { fg = fg, bg = bg_of("DiffDelete"), bold = true })
    end

    local function apply_overrides()
      set_headings()
      set_word_diff()
    end
    apply_overrides()
    vim.api.nvim_create_autocmd("ColorScheme", {
      group = vim.api.nvim_create_augroup("MarkviewHeadings", { clear = true }),
      callback = apply_overrides,
    })
  end,
}
