-- token (ThorstenRhau/token) — theme-mode family, the "token-meridian"
-- appearance only. Warm parchment over dark-classic accents: #272724 dark /
-- #fbf9f4 light. Loads eagerly (lazy = false, priority = 1000) so it's on the
-- rtp before config.lazy.lua's theme-sync.start().
--
-- The plugin ships five appearances; "token-meridian" is one colorscheme that
-- follows vim.o.background and registers colors_name "token-meridian" in both
-- modes, so theme-sync pins it.
return {
  "ThorstenRhau/token",
  name = "token",
  lazy = false,
  priority = 1000,
}
