return {
  {
    "sainnhe/sonokai",
    lazy = false,
    priority = 1000,
    config = function()
      vim.g.sonokai_style = "maia"
      vim.cmd.colorscheme("sonokai")
      vim.api.nvim_set_hl(0, "Directory", { fg = "#e3e1e4" })
      vim.api.nvim_set_hl(0, "MiniIconsAzure", { fg = "#9ecd6f" })
      vim.api.nvim_set_hl(0, "SnacksPickerGitStatusUntracked", { link = "DiagnosticWarn" })
      vim.api.nvim_set_hl(0, "SnacksPickerPathIgnored", { fg = "#848089" })
      vim.api.nvim_set_hl(0, "SnacksPickerPathHidden", { link = "Normal" })
    end,
  },
}
