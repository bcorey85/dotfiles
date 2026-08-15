-- monokai pro (loctvl842/monokai-pro.nvim) — the sole theme family, wired into
-- theme-mode/theme-sync. Loads eagerly (lazy = false, priority = 1000) so it's
-- on the rtp before config.lazy.lua's theme-sync.start(). `filter` picks the
-- default palette; theme-sync selects it by colorscheme name (monokai-pro).
-- Dark-only: no light variant exists, so light mode currently shows the dark
-- scheme (see theme-sync FAMILIES) until a light theme is chosen.
return {
  "loctvl842/monokai-pro.nvim",
  lazy = false,
  priority = 1000,
  opts = { filter = "pro" },
}
