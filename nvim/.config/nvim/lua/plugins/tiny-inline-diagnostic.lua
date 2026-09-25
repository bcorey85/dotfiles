-- tiny-inline-diagnostic.nvim — replaces the default virtual_text diagnostic
-- display with a prettier, cursor-line-focused inline render (only the current
-- line's diagnostics, wrapped and source-tagged).
--
-- The built-in `virtual_text` is disabled in config/lsp.lua (NOT here): plugin
-- setups run before `require("config.lsp")` in pack.lua, so anything this file
-- sets on vim.diagnostic.config would be clobbered by lsp.lua afterward. Signs,
-- underline, and the statusline counts are left to the native config.
return {
  "rachartier/tiny-inline-diagnostic.nvim",
  event = "VeryLazy",
  config = function()
    require("tiny-inline-diagnostic").setup({
      preset = "modern",
      -- A `signs` table makes the preset merge keep ours; without it the preset forces blend back to 0.22.
      signs = {},
      blend = { factor = 0.07 },
      options = {
        show_source = { enabled = true, if_many = true },
        multilines = { enabled = true, always_show = false },
        show_all_diags_on_cursorline = true,
      },
    })
  end,
}
