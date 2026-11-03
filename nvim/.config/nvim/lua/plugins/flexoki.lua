-- flexoki (kepano/flexoki-neovim) — theme-mode family. Dark #100f0f / paper
-- #fffcf0 light. Loads eagerly (lazy = false, priority = 1000) so it's on the
-- rtp before config.lazy.lua's theme-sync.start().
return {
  "kepano/flexoki-neovim",
  name = "flexoki",
  lazy = false,
  priority = 1000,
}
