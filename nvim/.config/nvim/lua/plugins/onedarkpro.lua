-- onedarkpro (olimorris/onedarkpro.nvim) — theme-mode family. Dark #282c34 /
-- light #fafafa. Loads eagerly (lazy = false, priority = 1000) so it's on the
-- rtp before config.lazy.lua's theme-sync.start().
return {
  "olimorris/onedarkpro.nvim",
  name = "onedarkpro",
  lazy = false,
  priority = 1000,
}
