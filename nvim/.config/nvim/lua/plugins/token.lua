-- token (ThorstenRhau/token) — two theme-mode families: token (warm graphite #262624 dark /
-- #faf9f5 light) and token-flint (cool grey #272c33 dark / #f5f7f8 light). The rest are
-- auditions: :colorscheme token-ultra, token-meridian or token-temper. Each follows 'background'. version = "*" takes the latest tagged release.
-- Loads eagerly (lazy = false, priority = 1000) so it's on the rtp before theme-sync.start().
return {
  "ThorstenRhau/token",
  version = "*",
  lazy = false,
  priority = 1000,
  -- No bold or italic in any token variant; the gate also covers plugin groups.
  opts = { attributes = { bold = false, italic = false } },
}
