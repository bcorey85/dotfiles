-- nightfox (EdenEast/nightfox.nvim) — vehicle for TWO theme-mode families:
-- `nightfox` (nightfox #192330 / dayfox #f6f2ee) and `duskfox` (duskfox
-- #232136 / dawnfox #faf4ed). Loads eagerly (lazy = false, priority = 1000)
-- so it's on the rtp before config.lazy.lua's theme-sync.start().
return {
  "EdenEast/nightfox.nvim",
  name = "nightfox",
  lazy = false,
  priority = 1000,
}
