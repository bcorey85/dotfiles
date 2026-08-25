-- flexoki (kepano/flexoki-neovim, the author's native version) — wired into
-- theme-mode/theme-sync. Loads eagerly (lazy = false, priority = 1000) so it's
-- on the rtp before config.lazy.lua's theme-sync.start(). Two distinct
-- colorschemes (flexoki-dark / flexoki-light) that both set colors_name
-- "flexoki", so theme-sync selects schemes[mode] and pins colors_name for
-- its override guard.
return {
  "kepano/flexoki-neovim",
  name = "flexoki",
  lazy = false,
  priority = 1000,
}
