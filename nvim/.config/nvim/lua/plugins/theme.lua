-- return {
--   {
--     "sainnhe/sonokai",
--     lazy = false,
--     priority = 1000,
--     config = function()
--       vim.g.sonokai_style = "shusia"
--       vim.cmd.colorscheme("sonokai")
--     end,
--   },
-- }
return {
  "sainnhe/gruvbox-material",
  lazy = false,
  priority = 1000,
  config = function()
    -- Optionally configure and load the colorscheme
    -- directly inside the plugin declaration.
    vim.g.gruvbox_material_enable_italic = true
    vim.g.gruvbox_material_foreground = "mix"
    vim.g.gruvbox_material_background = "medium"
    vim.cmd.colorscheme("gruvbox-material")
    vim.api.nvim_set_hl(0, "Directory", { fg = "#8bba7f" })
    vim.api.nvim_set_hl(0, "MiniIconsAzure", { fg = "#f2594b" })
  end,
}
