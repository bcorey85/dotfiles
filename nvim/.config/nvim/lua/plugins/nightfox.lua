-- nightfox (EdenEast/nightfox.nvim) — theme-mode family `nightfox`
-- (nightfox #192330 / dayfox #f6f2ee). Loads eagerly (lazy = false, priority = 1000)
-- so it's on the rtp before config.lazy.lua's theme-sync.start().
return {
  "EdenEast/nightfox.nvim",
  name = "nightfox",
  lazy = false,
  priority = 1000,
}
