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
      local purple = dark and "#ad5c7c" or "#6e33ce"
      local blue = dark and "#5a93aa" or "#2848a9"
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
    -- default to `reverse = true`. Reversing a dim token fg — terafox's comment
    -- (#6d7f8b) worst of all — paints dark-teal text on a muted-gray block:
    -- the changed WORDS in a reworded comment become nearly illegible. Replace
    -- reverse with terafox's own diff backgrounds + a forced bright Normal fg, so
    -- the emphasised word reads on ANY underlying token. Values are read from the
    -- resolved palette so this tracks the dayfox/terafox light↔dark toggle.
    local function set_word_diff()
      local hl = vim.api.nvim_set_hl
      local function bg_of(name)
        return vim.api.nvim_get_hl(0, { name = name, link = false }).bg
      end
      local fg = vim.api.nvim_get_hl(0, { name = "Normal", link = false }).fg
      -- DiffText (word-emphasis teal) sits a shade lighter than DiffChange (the
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
