-- kanso (webhooked/kanso.nvim, kanagawa lineage) — wired into theme-mode/
-- theme-sync. Loads eagerly (lazy = false, priority = 1000) so it's on the rtp
-- before config.lazy.lua's theme-sync.start(). Two distinct colorschemes
-- (kanso-zen / kanso-pearl) that both set the shared colors_name "kanso", so
-- theme-sync selects schemes[mode] and pins colors_name for its override guard.
return {
  "webhooked/kanso.nvim",
  name = "kanso",
  lazy = false,
  priority = 1000,
}
