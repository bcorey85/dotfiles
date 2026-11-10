-- token (ThorstenRhau/token) — token-flint is the theme-mode family (cool grey #272c33 dark /
-- #f5f7f8 light). The rest are auditions: :colorscheme token, token-ultra, token-meridian or
-- token-temper. Each follows 'background'. version = "*" takes the latest tagged release.
-- Loads eagerly (lazy = false, priority = 1000) so it's on the rtp before theme-sync.start().
return {
  "ThorstenRhau/token",
  version = "*",
  lazy = false,
  priority = 1000,
}
