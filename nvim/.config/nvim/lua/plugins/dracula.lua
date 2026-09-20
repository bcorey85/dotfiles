-- dracula (dracula/vim, the official port) — theme-mode family. Dark = dracula
-- / light = alucard, the official light half. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before config.lazy.lua's
-- theme-sync.start().
return {
  "dracula/vim",
  name = "dracula",
  lazy = false,
  priority = 1000,
}
