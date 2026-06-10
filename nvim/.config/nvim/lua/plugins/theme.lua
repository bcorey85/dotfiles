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
    })
    vim.cmd.colorscheme("catppuccin")
    vim.api.nvim_set_hl(0, "WhichKey", { fg = "#94e2d5" })
    vim.api.nvim_set_hl(0, "WhichKeyGroup", { fg = "#b4befe" })
    vim.api.nvim_set_hl(0, "WhichKeySeparator", { fg = "#6c7086" })
    vim.api.nvim_set_hl(0, "WhichKeyDesc", { fg = "#cdd6f4" })
    vim.api.nvim_set_hl(0, "WhichKeyBorder", { fg = "#94e2d5" })
    vim.api.nvim_set_hl(0, "WhichKeyTitle", { fg = "#94e2d5" })
    vim.api.nvim_set_hl(0, "@tag", { fg = "#94e2d5" })
    vim.api.nvim_set_hl(0, "@tag.builtin", { fg = "#94e2d5" })
    vim.api.nvim_set_hl(0, "@tag.attribute", { fg = "#b4befe" })
    vim.api.nvim_set_hl(0, "@tag.delimiter", { fg = "#6c7086" })
    vim.api.nvim_set_hl(0, "Directory", { fg = "#cdd6f4" })
    vim.api.nvim_set_hl(0, "MiniIconsAzure", { fg = "#a6e3a1" })
    vim.api.nvim_set_hl(0, "MiniIndentscopeSymbol", { fg = "#6c7086" })
    -- LSP document-highlight: underline instead of Catppuccin's
    -- background block (these are the groups document_highlight renders with).
    vim.api.nvim_set_hl(0, "LspReferenceText", { underline = true })
    vim.api.nvim_set_hl(0, "LspReferenceRead", { underline = true })
    vim.api.nvim_set_hl(0, "LspReferenceWrite", { underline = true })
    -- Word-level diff: changed words (DiffText, used by diffopt "inline:word")
    -- default to a near-white wash that's hard to read. Paint them on a
    -- saturated green background so reworded text stands out in :Gdiffsplit.
    vim.api.nvim_set_hl(0, "DiffText", { bg = "#2e5d3a", bold = true })
  end,
}
