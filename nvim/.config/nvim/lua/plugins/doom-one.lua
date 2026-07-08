-- doom-one — colorscheme plugin for the "doom-one" theme family. Which family
-- is active lives in ~/.cache/theme-family (theme-mode script); nvim-side
-- scheme mapping, mode sync, and the port-defect fixups (fg-only Diff*,
-- unreadable comments -> emacs brighter-comments values) all live in
-- lua/config/theme-sync.lua. This spec only declares the plugin and starts
-- the sync — it loads eagerly regardless of active family so theme-sync can
-- resolve any registered scheme at startup.
return {
  "NTBBloodbath/doom-one.nvim",
  lazy = false,
  priority = 1000,
  init = function()
    -- Options are plain globals read when the colorscheme applies.
    vim.g.doom_one_terminal_colors = true
    vim.g.doom_one_italic_comments = false
    vim.g.doom_one_enable_treesitter = true
  end,
  config = function()
    require("config.theme-sync").start()
  end,
}
