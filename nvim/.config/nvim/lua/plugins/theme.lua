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
          WhichKey = { fg = "#94e2d5" },
          WhichKeyGroup = { fg = "#b4befe" },
          WhichKeySeparator = { fg = "#6c7086" },
          WhichKeyDesc = { fg = "#cdd6f4" },
          WhichKeyBorder = { fg = "#94e2d5" },
          WhichKeyTitle = { fg = "#94e2d5" },
          ["@tag"] = { fg = "#94e2d5" },
          ["@tag.builtin"] = { fg = "#94e2d5" },
          ["@tag.attribute"] = { fg = "#b4befe" },
          ["@tag.delimiter"] = { fg = "#6c7086" },
          Directory = { fg = "#cdd6f4" },
          MiniIconsAzure = { fg = "#a6e3a1" },
          MiniIndentscopeSymbol = { fg = "#6c7086" },
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
