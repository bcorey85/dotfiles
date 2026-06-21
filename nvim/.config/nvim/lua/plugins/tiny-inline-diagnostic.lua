-- tiny-inline-diagnostic.nvim — replaces the default virtual_text diagnostic
-- display with a prettier, cursor-line-focused inline render (only the current
-- line's diagnostics, wrapped and source-tagged).
--
-- The built-in `virtual_text` is disabled in config/lsp.lua (NOT here): plugin
-- setups run before `require("config.lsp")` in pack.lua, so anything this file
-- sets on vim.diagnostic.config would be clobbered by lsp.lua afterward. Signs,
-- underline, and the statusline counts are left to the native config.
return {
  src = "rachartier/tiny-inline-diagnostic.nvim",
  setup = function()
    require("tiny-inline-diagnostic").setup({
      preset = "modern",
      options = {
        show_source = { enabled = true, if_many = true },
        multilines = { enabled = true, always_show = false },
        show_all_diags_on_cursorline = true,
      },
    })
  end,
}
