-- github (projekt0n/github-nvim-theme) — theme-mode family. Dimmed dark
-- #22272e / light default #ffffff: Atom-grade canvas, muted fg, vivid
-- primer accents, best-in-class light. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before config.lazy.lua's
-- theme-sync.start().
--
-- One colorscheme per variant ("github_dark_dimmed" /
-- "github_light_default"), each registering its own colors_name, so
-- theme-sync names them separately with no pin (thorn pattern). No setup()
-- call needed — the colorscheme files load their own variant.
return {
  "projekt0n/github-nvim-theme",
  name = "github-nvim-theme",
  lazy = false,
  priority = 1000,
}
