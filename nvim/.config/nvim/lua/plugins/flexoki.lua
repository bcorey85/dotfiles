-- flexoki (kepano/flexoki-neovim, the author's native version) — wired into
-- theme-mode/theme-sync. Loads eagerly (lazy = false, priority = 1000) so it's
-- on the rtp before config.lazy.lua's theme-sync.start(). One colorscheme
-- "flexoki" switches via vim.o.background, so theme-sync pins both the scheme
-- name and colors_name for its override guard.
return {
  "kepano/flexoki-neovim",
  name = "flexoki",
  lazy = false,
  priority = 1000,
}
