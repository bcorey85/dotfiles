-- monokai pro (loctvl842/monokai-pro.nvim) — one of the theme families (see
-- also flexoki.lua), wired into theme-mode/theme-sync. Loads eagerly
-- (lazy = false, priority = 1000) so it's
-- on the rtp before config.lazy.lua's theme-sync.start(). `filter` picks the
-- default palette; theme-sync selects the entry by colorscheme name
-- (monokai-pro dark / monokai-pro-light light — see theme-sync FAMILIES).
return {
  "loctvl842/monokai-pro.nvim",
  lazy = false,
  priority = 1000,
  opts = { filter = "pro" },
}
