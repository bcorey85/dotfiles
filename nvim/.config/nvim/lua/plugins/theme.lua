return {
  src = "NTBBloodbath/doom-one.nvim",
  name = "doom-one", -- derive_name would give "doom-one.nvim"; pin it explicitly
  setup = function()
    -- doom-one config is via vim.g globals (the setup() function was deprecated
    -- in 2022 in favour of these). doom-one's native base bg is #282c34 — the
    -- OneDark faded-black we target everywhere — so no palette override.
    vim.g.doom_one_cursor_coloring = false
    vim.g.doom_one_terminal_colors = true
    vim.g.doom_one_italic_comments = true
    vim.g.doom_one_enable_treesitter = true
    vim.g.doom_one_diagnostics_text_color = false
    vim.g.doom_one_transparent_background = false

    vim.cmd.colorscheme("doom-one")

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
