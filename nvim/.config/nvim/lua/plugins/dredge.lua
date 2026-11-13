-- dredge (bcorey85/dredge.nvim) — theme-mode family "dredge": syntax coloured by role.
-- The plugin ships the colorscheme, its lualine theme and the after/queries
-- highlight captures the roles read. Loads eagerly (lazy = false, priority = 1000)
-- so it's on the rtp before config.lazy.lua's theme-sync.start().
return {
  "bcorey85/dredge.nvim",
  name = "dredge",
  lazy = false,
  priority = 1000,
}
