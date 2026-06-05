return {
  {
    "catppuccin/nvim",
    name = "catppuccin",
    lazy = false,
    priority = 1000,
    opts = {
      flavour = "mocha",
      color_overrides = {
        mocha = {
          base = "#282c34",
          mantle = "#21252b",
          crust = "#1b1f27",
        },
      },
    },
    config = function(_, opts)
      require("catppuccin").setup(opts)
      vim.cmd.colorscheme("catppuccin")
      vim.api.nvim_set_hl(0, "WhichKey", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "WhichKeyGroup", { fg = "#b4befe" })
      vim.api.nvim_set_hl(0, "WhichKeySeparator", { fg = "#6c7086" })
      vim.api.nvim_set_hl(0, "WhichKeyDesc", { fg = "#cdd6f4" })
      vim.api.nvim_set_hl(0, "WhichKeyBorder", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "WhichKeyTitle", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksPickerMatch", { fg = "#94e2d5", bold = true })
      vim.api.nvim_set_hl(0, "SnacksPickerPrompt", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksPickerSpecial", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksPickerLabel", { fg = "#b4befe" })
      vim.api.nvim_set_hl(0, "SnacksPickerSpinner", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksPickerIcon", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksPickerToggle", { fg = "#b4befe" })
      vim.api.nvim_set_hl(0, "SnacksPickerBorder", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksDashboardHeader", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksDashboardIcon", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksDashboardKey", { fg = "#b4befe" })
      vim.api.nvim_set_hl(0, "SnacksDashboardTitle", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "SnacksDashboardDesc", { fg = "#cdd6f4" })
      vim.api.nvim_set_hl(0, "@tag", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "@tag.builtin", { fg = "#94e2d5" })
      vim.api.nvim_set_hl(0, "@tag.attribute", { fg = "#b4befe" })
      vim.api.nvim_set_hl(0, "@tag.delimiter", { fg = "#6c7086" })
      vim.api.nvim_set_hl(0, "Directory", { fg = "#cdd6f4" })
      vim.api.nvim_set_hl(0, "MiniIconsAzure", { fg = "#a6e3a1" })
      vim.api.nvim_set_hl(0, "SnacksPickerGitStatusUntracked", { link = "DiagnosticWarn" })
      vim.api.nvim_set_hl(0, "SnacksPickerPathIgnored", { fg = "#6c7086" })
      vim.api.nvim_set_hl(0, "SnacksPickerPathHidden", { link = "Normal" })
      vim.api.nvim_set_hl(0, "SnacksIndent", { fg = "#313244" })
      vim.api.nvim_set_hl(0, "SnacksIndentScope", { fg = "#6c7086" })
      -- snacks.words / LSP document-highlight: underline instead of Catppuccin's
      -- background block (these are the groups document_highlight renders with).
      vim.api.nvim_set_hl(0, "LspReferenceText", { underline = true })
      vim.api.nvim_set_hl(0, "LspReferenceRead", { underline = true })
      vim.api.nvim_set_hl(0, "LspReferenceWrite", { underline = true })
    end,
  },
}
