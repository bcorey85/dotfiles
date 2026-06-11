return {
  src = "catppuccin/nvim",
  name = "catppuccin",
  setup = function()
    require("catppuccin").setup({
      flavour = "mocha",
      color_overrides = {
        mocha = {
          base = "#282c34",
          mantle = "#21252b",
          crust = "#1b1f27",
        },
      },
      -- custom_highlights is re-applied by catppuccin on every :colorscheme
      -- call, so these survive re-application unlike bare nvim_set_hl() calls.
      custom_highlights = function()
        return {
          -- Float chrome baseline: teal borders, red titles on mantle. Every float that
          -- links to FloatBorder/FloatTitle (mini.pick, tiny-cmdline, LSP floats,
          -- ui-input, blink docs) inherits this — single source of truth, no blue UI.
          -- Small red pop keeps red-as-accent without red-framing every float.
          FloatBorder = { fg = "#94e2d5", bg = "#21252b" },
          FloatTitle = { fg = "#f38ba8", bg = "#21252b" },
          -- catppuccin paints the blink menu border blue directly (not via link);
          -- re-link it to the FloatBorder baseline so the completion menu matches.
          BlinkCmpMenuBorder = { link = "FloatBorder" },
          -- mini.clue: Catppuccin Mocha palette ported to MiniClue* groups.
          MiniClueNextKey = { fg = "#94e2d5" },
          MiniClueDescGroup = { fg = "#b4befe" },
          MiniClueDescSingle = { fg = "#cdd6f4" },
          MiniClueSeparator = { fg = "#6c7086" },
          MiniClueBorder = { link = "FloatBorder" },
          MiniClueTitle = { link = "FloatTitle" },
          -- Submode keys (e.g. <C-w> resize): red so it's obvious these keys repeat
          -- without re-entering the prefix.
          MiniClueNextKeyWithPostkeys = { fg = "#f38ba8", bold = true },
          ["@tag"] = { fg = "#94e2d5" },
          ["@tag.builtin"] = { fg = "#94e2d5" },
          ["@tag.attribute"] = { fg = "#b4befe" },
          ["@tag.delimiter"] = { fg = "#6c7086" },
          Directory = { fg = "#cdd6f4" },
          MiniIconsAzure = { fg = "#a6e3a1" },
          MiniIndentscopeSymbol = { fg = "#6c7086" },
          -- Selected row: bg-only surface0, matching blink's PmenuSel, so "current
          -- item" reads identically in the picker and the completion menu.
          MiniPickMatchCurrent = { bg = "#313244", fg = "NONE" },
          -- mini.pick title/info text in the border: lavender (palette: teal chrome,
          -- red titles, lavender identity). Catppuccin's default here is mauve.
          -- Note: titles are red globally, but picker identity stays lavender per design.
          MiniPickBorderText = { fg = "#b4befe", bg = "#21252b" },
          -- LSP document-highlight: underline instead of Catppuccin's
          -- background block (these are the groups document_highlight renders with).
          LspReferenceText = { underline = true },
          LspReferenceRead = { underline = true },
          LspReferenceWrite = { underline = true },
          -- Word-level diff: changed words (DiffText, used by diffopt "inline:word")
          -- default to a near-white wash that's hard to read. Paint them on a
          -- saturated green background so reworded text stands out in :Gdiffsplit.
          DiffText = { bg = "#2e5d3a", bold = true },
          -- treesitter-context sticky header: lift it off the buffer with the same
          -- surface tone the statusline badges use (#313244) so it reads as chrome,
          -- not code, and underline the bottom edge in teal to mark exactly where
          -- the sticky block ends and real buffer lines begin.
          TreesitterContext = { bg = "#313244" },
          TreesitterContextLineNumber = { fg = "#6c7086", bg = "#313244" },
          TreesitterContextBottom = { underline = true, sp = "#94e2d5" },
          TreesitterContextLineNumberBottom = { underline = true, sp = "#94e2d5" },
        }
      end,
    })
    vim.cmd.colorscheme("catppuccin")
  end,
}
